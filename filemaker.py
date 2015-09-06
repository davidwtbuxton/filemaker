#!/usr/bin/env python
"""Efficient importer for Filemaker XML.

A tool for importing to Django data exported from Filemaker Pro in XML. When
exporting, choose XML with FMPXMLRESULT grammar.
"""


from xml.sax.handler import ContentHandler, ErrorHandler
import collections
import datetime
import re
import time
import xml.sax


FMP_ELEMENTS = (
    'FMPXMLRESULT',
    'METADATA',
    'FIELD',
    'RESULTSET',
    'ROW',
    'COL',
    'DATA',
    'ERRORCODE',
    'PRODUCT',
    'DATABASE',
)


DEFAULT_DATEFMT = '%Y/%m/%d'


class FMPImporter(object):
    """Provides a mapping between a Filemaker record and a Django record.

    fields is a dictionary with field names as keys and values a four-tuple of
    ('field_name', 'TYPE', MAXREPEAT, allowempty)

    """
    def __init__(self, datefmt=None):
        self.fields = collections.OrderedDict()
        self.datefmt = datefmt or DEFAULT_DATEFMT
        self.database = XMLNode('DATABASE')

    def add_field(self, node):
        name = node.attrs['NAME']
        kind = node.attrs['TYPE']
        maxrepeat = int(node.attrs['MAXREPEAT'])
        empty = False
        if node.attrs['EMPTYOK'] == 'YES':
            empty = True

        self.fields[name] = (name, kind, maxrepeat, empty)

    def add_database(self, node):
        """Add database information including date / time formats."""
        self.database = node

    def field_names(self):
        return self.fields.keys()

    def format_dict(self, dic):
        """Returns a new dict with values formatted according to the known
        Filemaker field definitions.
        """
        new_dic = collections.OrderedDict()
        for key in dic:
            name, kind, maxrepeat, empty = self.fields[key]
            try:
                value = self.format_value(name, kind, dic[key], dic, maxrepeat, empty)
            except ValueError:
                print "Couldn't format column %s:'%s' as %s" % (name, dic[key], kind)
                raise
            new_dic[key] = value

        return new_dic

    def format_node(self, node):
        """Returns a new dict for the XML node."""
        vals = [data.text for col in node.children for data in col.children]
        row = collections.OrderedDict(zip(self.field_names(), vals))
        return self.format_dict(row)

    def format_value(self, name, kind, value, row, maxrepeat=None, empty=True):
        if kind == 'NUMBER':
            return self.format_number(name, kind, value, row, maxrepeat, empty)
        elif kind == 'DATE':
            return self.format_date(name, kind, value, row, maxrepeat, empty)
        elif kind == 'TIME':
            return self.format_time(name, kind, value, row, maxrepeat, empty)
        else:
            return self.format_text(name, kind, value, row, maxrepeat, empty)

    def format_number(self, name, kind, value, row, maxrepeat=None, empty=True):
        """Returns the value as a float instance."""
        value = re.sub(r'[^\.\d]', '', value)
        if value == '':
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def format_date(self, name, kind, value, row, maxrepeat=None, empty=True):
        """Returns the value as a date instance."""
        if value == '':
            return None
        t = time.strptime(value, self.datefmt)
        return datetime.date(*t[:3])

    def format_time(self, name, kind, value, row, maxrepeat=None, empty=True):
        """Returns the value as a datetime.time instance."""
        return flexitime(value) or datetime.time()

    def format_text(self, name, kind, value, row, maxrepeat=None, empty=True):
        """Returns the value as a Unicode string with trailing whitespace
        stripped.
        """
        return unicode(value).strip()

    def import_node(self, node):
        """Convert an XML node to a more useful dictionary."""
        print node.attrs['RECORDID']


class XMLNode(object):
    def __init__(self, name, attrs=None, text=None, children=None):
        self.name = name
        self.attrs = attrs or {}
        self.text = text or ''
        self.children = children or []

    def __repr__(self):
        s = super(XMLNode, self).__repr__()
        idx = s.find(' ')
        return s[:idx] + ' ' + self.name + s[idx:]


class FMPXMLHandler(ContentHandler):
    def __init__(self, importer=None):
        self.importer = importer or FMPImporter()
        self._depth = []

    def setDocumentLocator(self, locator):
        """Called by parser to give the location of document events."""

    def startElement(self, name, attrs):
        """Signals the start of an element in non-namespace mode."""
        node = XMLNode(name, attrs)
        self.push_node(node)

    def endElement(self, name):
        """Signals the end of an element in non-namespace mode."""
        node = self.pop_node()
        if name == 'DATABASE':
            self.importer.add_database(node)
        elif name == 'FIELD':
            self.importer.add_field(node)
        elif name == 'ROW':
            self.importer.import_node(node)
            # Delete the reference from the parent node to free memory
            self.current_node.children[:] = self.current_node.children[:-1]

    def characters(self, content):
        """Receives notification of character data."""
        node = self.current_node
        if node.name in ('ROW', 'COL', 'DATA'):
            node.text += content

    def push_node(self, node):
        """Append the node as a child to the current node and make it the
        current node.
        """
        if self.current_node:
            self.current_node.children.append(node)

        self._depth.append(node)

    def pop_node(self):
        """Return the current node."""
        return self._depth.pop()

    @property
    def current_node(self):
        """Return the current node or the root node."""
        if self._depth:
            return self._depth[-1]
        else:
            return None


def flexitime(value):
    """Return a datetime.time object for the string or None.

    >>> flexitime('12:00:00')
    datetime.time(12, 0)
    >>> flexitime('12:00:59')
    datetime.time(12, 0, 59)
    >>> flexitime('23:30:59')
    datetime.time(23, 30, 59)
    >>> flexitime('3:30:59')
    datetime.time(3, 30, 59)
    >>> flexitime('3:30')
    datetime.time(3, 30)
    >>> flexitime('3:30 pm')
    datetime.time(15, 30)
    >>> flexitime('3:30 am')
    datetime.time(3, 30)
    >>> flexitime('3.30 am')
    datetime.time(3, 30)
    >>> flexitime('3.30 pm')
    datetime.time(15, 30)
    >>> flexitime('3.3 pm')
    datetime.time(15, 3)
    >>> flexitime('3.3pm')
    datetime.time(15, 3)
    >>> flexitime('24:00')
    datetime.time(0, 0)
    >>> flexitime('')
    >>> flexitime('undefined')
    >>> flexitime(' 123')
    >>> flexitime(' 12.50  ')
    datetime.time(12, 50)
    """
    pat = re.compile(r'(?P<hours>\d{1,2})[\.:](?P<minutes>\d{1,2})([\.:](?P<seconds>\d{1,2}))? ?(?P<ampm>[Ap][Mm])?')
    matches = pat.search(value)
    if matches:
        parts = matches.groupdict()
        h, m, s = int(parts['hours']), int(parts['minutes']), int(parts['seconds'] or 0)
        if parts['ampm'] and (parts['ampm'].lower() == 'pm') and h < 12:
            h += 12
        if h > 23:
            h = 0
        return datetime.time(h, m, s)


def importfile(filename, importer=None):
    """Import a file using the given FMPImporter instance."""
    xml.sax.parse(filename, FMPXMLHandler(importer=importer))


def main(argv):
    importfile(argv[1])


if __name__ == "__main__":
    import sys

    main(sys.argv)
