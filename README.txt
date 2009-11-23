To use this module create a sub-class of the FMPImporter class and over-ride the
FMPImporter.import_node method. This method is called for each row of data in
the XML file and is passed an XML node instance for the row. You can convert
that node to a more useful dictionary where keys are column names and values are
the column values. You would then convert the data to your Django model object
and save it.

A trivial example:


    import filemaker
    
    class MyImporter(filemaker.FMPImporter):
        def import_node(self, node):
            node_dict = self.format_node(node)
            print node['RECORDID'], node_dict
    
    importer = MyImporter(datefmt='%d/%m/%Y')
    filemaker.importfile('/path/to/data.xml', importer=importer)


The FMPImporter.format_node method converts values to an appropriate Python type
according to the Filemaker column type. Filemaker’s DATE and TIME types are
converted to Python datetime.date and datetime.time instances respectively.
NUMBER types are converted to Python float instances. Everything else is left as
strings, but you can customize the conversion by over-riding the appropriate
methods in your sub-class (see the source for the appropriate method names).

In the case of Filemaker DATE values you can pass the datefmt argument to your
sub-class to specify the date format string. See Python’s time.strptime
documentation for the complete list of the format specifiers.

The code uses Python’s built-in SAX parser so that it is efficent when importing
huge XML files (the process uses a constant 15 megabytes for any size of data on
my Mac running Python 2.5).