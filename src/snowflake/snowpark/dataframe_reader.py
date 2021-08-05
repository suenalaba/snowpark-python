#
# Copyright (c) 2012-2021 Snowflake Computing Inc. All right reserved.
#

from typing import Dict

from snowflake.snowpark.dataframe import DataFrame
from snowflake.snowpark.internal.analyzer.analyzer_package import AnalyzerPackage
from snowflake.snowpark.internal.analyzer.sf_attribute import Attribute
from snowflake.snowpark.snowpark_client_exception import SnowparkClientException
from snowflake.snowpark.types.sf_types import StructType, VariantType


class DataFrameReader:
    """Provides methods to load data in various supported formats from a Snowflake
    stage to a DataFrame. The paths provided to the DataFrameReader must refer to
    Snowflake stages.

    To use this object:

    1. Access an instance of a DataFrameReader by calling the :obj:`Session.read()`
    method.

    2. Specify any `format-specific options <https://docs.snowflake.com/en/sql-reference/sql/create-file-format.html#format-type-options-formattypeoptions>`_ and `copy options <https://docs.snowflake.com/en/sql-reference/sql/copy-into-table.html#copy-options-copyoptions>`_
    by calling the :obj:`option` or :obj:`options` method. These methods return a
    DataFrameReader that is configured with these options. (Note that although
    specifying copy options can make error handling more robust during the reading
    process, it may have an effect on performance.)

    3. Specify the schema of the data that you plan to load by constructing a StructType
    object and passing it to the :obj:`schema` method. This method returns a
    DataFrameReader that is configured to read data that uses the specified schema.

    4. Specify the format of the data by calling the method named after the format
    (e.g. :obj:`csv`, :obj:`json`, etc.). These methods return a :obj:`DataFrame` that
    is configured to load data in the specified format.

    5. Call a :obj:`DataFrame` method that performs an action (e.g. :py:func:`DataFrame.collect`) to load the data from the file.

    The following examples demonstrate how to use a DataFrameReader.

    Example 1:
        Loading the first two columns of a CSV file and skipping the first header line::

            # Import the module for StructType.
            from snowflake.snowpark.types.sf_types import *
            file_path = "@mystage1"
            # Define the schema for the data in the CSV file.
            user_schema = StructType([StructField("a", IntegerType()), StructField("b", StringType())])
            # Create a DataFrame that is configured to load data from the CSV file.
            df = session.read.option("skip_header", 1).schema(user_schema).csv(file_path)
            # Load the data into the DataFrame and return an Array of Rows containing the results.
            results = df.collect()


    Example 2:
        Loading a gzip compressed json file::

            file_path = "@mystage2/data.json.gz"
            # Create a DataFrame that is configured to load data from the gzipped JSON file.
            json_df = session.read.option("compression", "gzip").json(file_path)
            # Load the data into the DataFrame and return an Array of Rows containing the results.
            results = json_df.collect()


      In addition, if you want to load only a subset of files from the stage, you can use the
      `pattern <https://docs.snowflake.com/en/sql-reference/sql/copy-into-table.html#loading-using-pattern-matching>`_
      option to specify a regular expression that matches the files that you want to load.

    Example 3:
        Loading only the CSV files from a stage location::

            from snowflake.snowpark.types.sf_types import *
            # Define the schema for the data in the CSV files.
            user_schema: StructType = StructType(Seq(StructField("a", IntegerType()),StructField("b", StringType())))
            # Create a DataFrame that is configured to load data from the CSV files in the stage.
            csv_df = session.read.option("pattern", ".[.]csv").schema(user_schema).csv("@stage_location")
            # Load the data into the DataFrame and return an Array of Rows containing the results.
            results = csv_df.collect()
    """

    def __init__(self, session):
        self.session = session
        self.__user_schema = None
        self.__cur_options = {}

    def table(self, name: str) -> DataFrame:
        """Returns a :obj:`DataFrame` that is set up to load data from the specified
        table.

        For the ``name`` argument, you can specify an unqualified name (if the table
        is in the current database and schema) or a fully qualified name
        (``db.schema.name``).

        Note that the data is not loaded in the DataFrame until you call a method that
        performs an action (e.g. :func:`DataFrame.collect`,
        :obj:`DataFrame.count`, etc.)."""
        return self.session.table(name)

    def schema(self, schema: StructType) -> "DataFrameReader":
        """Returns a ``DataFrameReader`` instance with the specified schema configuration
         for the data to be read.

        To define the schema for the data that you want to read, use a
        :obj:`sf_types.StructType` object.
        """
        self.__user_schema = schema
        return self

    def csv(self, path: str) -> DataFrame:
        """Returns a ``DataFrame`` that is set up to load data from the specified CSV
        file.

        This method only supports reading data from files in Snowflake stages.

        Note that the data is not loaded in the DataFrame until you call a method that
        performs an action (e.g. :obj:`DataFrame.collect`, :obj:`DataFrame.count`, etc.).

        Example::

            file_path = "@mystage1/myfile.csv"
            # Create a DataFrame that uses a DataFrameReader to load data from a file
            # in a stage.
            df = session.read.schema(user_schema).csv(fileInAStage).filter(col("a") < 2)
            # Load the data into the DataFrame and return an Array of Rows containing the results.
            results = df.collect()
        """
        if not self.__user_schema:
            raise SnowparkClientException(
                "Must provide user schema before reading file"
            )
        return DataFrame(
            self.session,
            self.session._Session__plan_builder.read_file(
                path,
                "csv",
                self.__cur_options,
                self.session.getFullyQualifiedCurrentSchema(),
                self.__user_schema.to_attributes(),
            ),
        )

    def json(self, path: str) -> DataFrame:
        r"""Returns a ``DataFrame`` that is set up to load data from the specified JSON file.

        This method only supports reading data from files in Snowflake stages.

        Note that the data is not loaded in the DataFrame until you call a method that performs
        an action (e.g. :obj:`DataFrame.collect`, :obj:`DataFrame.count`, etc.).

        Example::

          # Create a DataFrame that uses a DataFrameReader to load data from a file in a stage.
          df = session.read.json(path).where(col("\$1:num") > 1)
          # Load the data into the DataFrame and return an Array of Rows containing the results.
          results = df.collect()
        """
        return self.__read_semi_structured_file(path, "JSON")

    def avro(self, path: str) -> DataFrame:
        """Returns a ``DataFrame`` that is set up to load data from the specified Avro
        file.

        This method only supports reading data from files in Snowflake stages.

        Note that the data is not loaded in the DataFrame until you call a method that
        performs an action (e.g. :obj:`DataFrame.collect`, :obj:`DataFrame.count`, etc.)."""
        return self.__read_semi_structured_file(path, "AVRO")

    def parquet(self, path: str) -> DataFrame:
        r"""Returns a ``DataFrame`` that is set up to load data from the specified
        Parquet file.

        This method only supports reading data from files in Snowflake stages.

        Note that the data is not loaded in the DataFrame until you call a method that
        performs an action (e.g. :obj:`DataFrame.collect`, :obj:`DataFrame.count`, etc.).

        Example::

            # Create a DataFrame that uses a DataFrameReader to load data from a file in
            # a stage.
            df = session.read.parquet(path).where(col("\$1:num") > 1)
            # Load the data into the DataFrame and return an Array of Rows containing
            # the results.
            results = df.collect()
        """
        return self.__read_semi_structured_file(path, "PARQUET")

    def orc(self, path: str) -> DataFrame:
        r"""Returns a ``DataFrame`` that is set up to load data from the specified ORC file.

        This method only supports reading data from files in Snowflake stages.

        Note that the data is not loaded in the DataFrame until you call a method that performs
        an action (e.g. :obj:`DataFrame.collect`, :obj:`DataFrame.count`, etc.).

        Example::

            # Create a DataFrame that uses a DataFrameReader to load data from a file in a stage.
            df = session.read.orc(path).where(col("\$1:num") > 1)
            # Load the data into the DataFrame and return an Array of Rows containing the results.
            results = df.collect()
        """
        return self.__read_semi_structured_file(path, "ORC")

    def xml(self, path: str) -> DataFrame:
        """Returns a ``DataFrame`` that is set up to load data from the specified XML file.

        This method only supports reading data from files in Snowflake stages.

        Note that the data is not loaded in the DataFrame until you call a method that performs
        an action (e.g. :obj:`DataFrame.collect`, :obj:`DataFrame.count`, etc.).

        Example::

            # Create a DataFrame that uses a DataFrameReader to load data from a file in a stage.
            df = session.read.xml(path).where(col("xmlget(\\$1, 'num', 0):\"$\"") > 1)
            # Load the data into the DataFrame and return an Array of Rows containing the results.
            results = df.collect()
        """
        return self.__read_semi_structured_file(path, "XML")

    def option(self, key: str, value) -> "DataFrameReader":
        """Sets the specified option in the DataFrameReader.

        Use this method to configure any
        `format-specific options <https://docs.snowflake.com/en/sql-reference/sql/create-file-format.html#format-type-options-formattypeoptions>`_
        and
        `copy options <https://docs.snowflake.com/en/sql-reference/sql/copy-into-table.html#copy-options-copyoptions>`_.
        (Note that although specifying copy options can make error handling more robust during the
        reading process, it may have an effect on performance.)

        Example 1:
            Loading a LZO compressed Parquet file::

                # Create a DataFrame that uses a DataFrameReader to load data from a file in a stage.
                df = session.read.option("compression", "lzo").parquet(file_path)
                # Load the data into the DataFrame and return an Array of Rows containing the results.
                results = df.collect()

        Example 2:
            Loading an uncompressed JSON file::

                # Create a DataFrame that uses a DataFrameReader to load data from a file in a stage.
                df = session.read.option("compression", "none").json(file_path)
                # Load the data into the DataFrame and return an Array of Rows containing the results.
                results = df.collect()

        Example 3:
            Loading the first two columns of a colon-delimited CSV file in which the
            first line is the header::

              from snowflake.snowpark.types.sf_types import *
              # Define the schema for the data in the CSV files.
              user_schema = StructType(Seq(StructField("a", IntegerType()), StructField("b", StringType())))
              # Create a DataFrame that is configured to load data from the CSV file.
              csv_df = session.read.option("field_delimiter", ";").option("skip_header", 1).schema(user_schema).csv(file_path)
              # Load the data into the DataFrame and return an Array of Rows containing the results.
              results = csv_df.collect()

        In addition, if you want to load only a subset of files from the stage, you can use the
        `pattern <https://docs.snowflake.com/en/sql-reference/sql/copy-into-table.html#loading-using-pattern-matching>`_
        option to specify a regular expression that matches the files that you want to load.

        Example 4:
            Loading only the CSV files from a stage location::

                from snowflake.snowpark.types.sf_types import *
                # Define the schema for the data in the CSV files.
                user_schema = StructType(Seq(StructField("a", IntegerType()),StructField("b", StringType())))
                # Create a DataFrame that is configured to load data from the CSV files in the stage.
                csv_df = session.read.option("pattern", ".[.]csv").schema(user_schema).csv("@stage_location")
                # Load the data into the DataFrame and return an Array of Rows containing the results.
                results = csv_df.collect()
        """
        self.__cur_options[key.upper()] = self.__parse_value(value)
        return self

    def options(self, configs: Dict) -> "DataFrameReader":
        """Sets multiple specified options in the DataFrameReader.

        Use this method to configure any
        `format-specific options <https://docs.snowflake.com/en/sql-reference/sql/create-file-format.html#format-type-options-formattypeoptions>`_
        and
        `copy options <https://docs.snowflake.com/en/sql-reference/sql/copy-into-table.html#copy-options-copyoptions>`_.
        (Note that although specifying copy options can make error handling more robust during the
        reading process, it may have an effect on performance.)

        In addition, if you want to load only a subset of files from the stage, you can use the
        `pattern <https://docs.snowflake.com/en/sql-reference/sql/copy-into-table.html#loading-using-pattern-matching>`_
        option to specify a regular expression that matches the files that you want to load.

        Example:
            Loading a LZO compressed Parquet file and removing any white space from the
            fields::

                # Create a DataFrame that uses a DataFrameReader to load data from a file in a stage.
                df = session.read.option(Map("compression"-> "lzo", "trim_space" -> true)).parquet(file_path)
                # Load the data into the DataFrame and return an Array of Rows containing the results.
                results = df.collect()
        """
        for k, v in configs.items():
            self.option(k, v)
        return self

    def __parse_value(self, v) -> str:
        if type(v) in [bool, int]:
            return str(v)
        elif type(v) == str and v.lower() in ["true", "false"]:
            return v
        else:
            return AnalyzerPackage.single_quote(str(v))

    def __read_semi_structured_file(self, path: str, format: str) -> "DataFrame":
        if self.__user_schema:
            raise ValueError(f"Read {format} does not support user schema")
        return DataFrame(
            self.session,
            self.session._Session__plan_builder.read_file(
                path,
                format,
                self.__cur_options,
                self.session.getFullyQualifiedCurrentSchema(),
                [Attribute('"$1"', VariantType())],
            ),
        )