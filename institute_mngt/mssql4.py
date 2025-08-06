import re
import sys
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

@dataclass
class ColumnDefinition:
    name: str
    data_type: str
    length: Optional[str] = None
    precision: Optional[str] = None
    scale: Optional[str] = None
    nullable: bool = True
    default_value: Optional[str] = None
    auto_increment: bool = False
    comment: Optional[str] = None
    charset: Optional[str] = None
    collation: Optional[str] = None

@dataclass
class IndexDefinition:
    name: str
    type: str  # PRIMARY, UNIQUE, INDEX, FULLTEXT, SPATIAL
    columns: List[str] = field(default_factory=list)
    length: Optional[Dict[str, int]] = field(default_factory=dict)

@dataclass
class ConstraintDefinition:
    name: str
    type: str  # FOREIGN KEY, CHECK, etc.
    columns: List[str] = field(default_factory=list)
    reference_table: Optional[str] = None
    reference_columns: List[str] = field(default_factory=list)
    on_delete: Optional[str] = None
    on_update: Optional[str] = None
    check_condition: Optional[str] = None

@dataclass
class TableDefinition:
    name: str
    columns: List[ColumnDefinition] = field(default_factory=list)
    indexes: List[IndexDefinition] = field(default_factory=list)
    constraints: List[ConstraintDefinition] = field(default_factory=list)
    engine: Optional[str] = None
    charset: Optional[str] = None
    collation: Optional[str] = None
    comment: Optional[str] = None
    auto_increment: Optional[int] = None

class MySQLToMSSQLConverter:
    def __init__(self):
        self.datatype_mapping = {
            # Integer types
            'TINYINT': 'TINYINT',
            'SMALLINT': 'SMALLINT', 
            'MEDIUMINT': 'INT',
            'INT': 'INT',
            'INTEGER': 'INT',
            'BIGINT': 'BIGINT',
            'BIT': 'BIT',
            
            # Decimal types
            'DECIMAL': 'DECIMAL',
            'NUMERIC': 'NUMERIC',
            'FLOAT': 'FLOAT',
            'DOUBLE': 'FLOAT',
            'REAL': 'REAL',
            
            # String types
            'CHAR': 'CHAR',
            'VARCHAR': 'VARCHAR',
            'TINYTEXT': 'VARCHAR(255)',
            'TEXT': 'TEXT',
            'MEDIUMTEXT': 'TEXT',
            'LONGTEXT': 'TEXT',
            'BINARY': 'BINARY',
            'VARBINARY': 'VARBINARY',
            'TINYBLOB': 'VARBINARY(255)',
            'BLOB': 'VARBINARY(MAX)',
            'MEDIUMBLOB': 'VARBINARY(MAX)',
            'LONGBLOB': 'VARBINARY(MAX)',
            
            # Date and time types
            'DATE': 'DATE',
            'TIME': 'TIME',
            'DATETIME': 'DATETIME2',
            'TIMESTAMP': 'DATETIME2',
            'YEAR': 'SMALLINT',
            
            # JSON and other types
            'JSON': 'NVARCHAR(MAX)',
            'GEOMETRY': 'GEOMETRY',
            'POINT': 'GEOMETRY',
            'LINESTRING': 'GEOMETRY',
            'POLYGON': 'GEOMETRY',
            'MULTIPOINT': 'GEOMETRY',
            'MULTILINESTRING': 'GEOMETRY',
            'MULTIPOLYGON': 'GEOMETRY',
            'GEOMETRYCOLLECTION': 'GEOMETRY',
            
            # Set and Enum (converted to constraints)
            'ENUM': 'VARCHAR',
            'SET': 'VARCHAR'
        }
        
    def convert_schema(self, mysql_schema: str) -> str:
        """Convert complete MySQL schema to MS SQL Server"""
        print("DEBUG: Starting conversion...")
        tables = self.parse_mysql_schema(mysql_schema)
        print(f"DEBUG: Parsed {len(tables)} tables")
        
        if not tables:
            print("DEBUG: No tables found! Returning error message.")
            return "-- ERROR: No tables found in the provided schema\n-- Please check your MySQL CREATE TABLE syntax"
        
        mssql_schema = self.generate_mssql_schema(tables)
        return mssql_schema
    
    def parse_mysql_schema(self, schema: str) -> List[TableDefinition]:
        """Parse MySQL schema and extract table definitions"""
        tables = []
        
        # Remove comments and normalize whitespace
        schema = self.clean_schema(schema)
        
        # Add semicolon if not present (for single table queries)
        schema = schema.strip()
        if not schema.endswith(';'):
            schema += ';'
        
        # Find CREATE TABLE and manually parse to handle nested parentheses correctly
        create_table_start = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([^`\s\(]+)`?\s*\(', schema, re.IGNORECASE)
        
        if not create_table_start:
            print("DEBUG: No CREATE TABLE statement found")
            return tables
        
        table_name = create_table_start.group(1).strip('`')
        print(f"DEBUG: Found table: {table_name}")
        
        # Find the opening parenthesis after table name
        start_pos = create_table_start.end() - 1  # Position of opening parenthesis
        
        # Manually find matching closing parenthesis
        paren_count = 0
        end_pos = start_pos
        in_quotes = False
        quote_char = None
        
        for i, char in enumerate(schema[start_pos:], start_pos):
            if char in ('"', "'", "`") and not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
            elif not in_quotes:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        end_pos = i
                        break
        
        if paren_count != 0:
            print("DEBUG: Unmatched parentheses in table definition")
            return tables
        
        # Extract table body (everything between the parentheses)
        table_body = schema[start_pos + 1:end_pos]
        
        # Extract table options (everything after closing parenthesis until semicolon)
        table_options = schema[end_pos + 1:].split(';')[0].strip()
        
        print(f"DEBUG: Table body length: {len(table_body)}")
        print(f"DEBUG: Table body preview: {table_body[:100]}...")
        print(f"DEBUG: Table options: {table_options}")
        
        # Parse table options
        engine = None
        charset = None
        collation = None
        comment = None
        auto_increment = None
        
        if table_options:
            engine_match = re.search(r'ENGINE\s*=\s*(\w+)', table_options, re.IGNORECASE)
            if engine_match:
                engine = engine_match.group(1)
            
            charset_match = re.search(r'(?:DEFAULT\s+)?CHARSET\s*=\s*(\w+)', table_options, re.IGNORECASE)
            if charset_match:
                charset = charset_match.group(1)
            
            collation_match = re.search(r'COLLATE\s*=\s*([^\s;]+)', table_options, re.IGNORECASE)
            if collation_match:
                collation = collation_match.group(1)
            
            comment_match = re.search(r'COMMENT\s*=\s*[\'"]([^\'"]*)[\'"]', table_options, re.IGNORECASE)
            if comment_match:
                comment = comment_match.group(1)
            
            # Parse AUTO_INCREMENT value
            auto_increment_match = re.search(r'AUTO_INCREMENT\s*=\s*(\d+)', table_options, re.IGNORECASE)
            if auto_increment_match:
                auto_increment = int(auto_increment_match.group(1))
                print(f"DEBUG: Found AUTO_INCREMENT={auto_increment}")
        
        table = TableDefinition(
            name=table_name,
            engine=engine,
            charset=charset,
            collation=collation,
            comment=comment,
            auto_increment=auto_increment
        )
        
        self.parse_table_body(table, table_body)
        tables.append(table)
        print(f"DEBUG: Added table with {len(table.columns)} columns, {len(table.indexes)} indexes")
        
        return tables
    
    def clean_schema(self, schema: str) -> str:
        """Remove comments and clean up schema"""
        # Remove single line comments
        schema = re.sub(r'--.*$', '', schema, flags=re.MULTILINE)
        
        # Remove multi-line comments
        schema = re.sub(r'/\*.*?\*/', '', schema, flags=re.DOTALL)
        
        # Normalize whitespace
        schema = re.sub(r'\s+', ' ', schema)
        
        return schema.strip()
    
    def parse_table_body(self, table: TableDefinition, body: str):
        """Parse table body for columns, indexes, and constraints"""
        # Split by commas, but be careful of nested parentheses
        elements = self.split_table_elements(body)
        
        for element in elements:
            element = element.strip()
            if not element:
                continue
                
            if element.upper().startswith('PRIMARY KEY'):
                self.parse_primary_key(table, element)
            elif element.upper().startswith('UNIQUE'):
                self.parse_unique_key(table, element)
            elif element.upper().startswith('KEY') or element.upper().startswith('INDEX'):
                self.parse_index(table, element)
            elif element.upper().startswith('FULLTEXT'):
                self.parse_fulltext_index(table, element)
            elif element.upper().startswith('SPATIAL'):
                self.parse_spatial_index(table, element)
            elif element.upper().startswith('FOREIGN KEY') or element.upper().startswith('CONSTRAINT'):
                self.parse_constraint(table, element)
            elif element.upper().startswith('CHECK'):
                self.parse_check_constraint(table, element)
            else:
                # Assume it's a column definition
                self.parse_column(table, element)
    
    def split_table_elements(self, body: str) -> List[str]:
        """Split table body by commas, respecting parentheses"""
        elements = []
        current_element = ""
        paren_count = 0
        in_quotes = False
        quote_char = None
        
        for char in body:
            if char in ('"', "'", "`") and not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
            elif not in_quotes:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                elif char == ',' and paren_count == 0:
                    elements.append(current_element.strip())
                    current_element = ""
                    continue
            
            current_element += char
        
        if current_element.strip():
            elements.append(current_element.strip())
        
        return elements
    
    def parse_column(self, table: TableDefinition, definition: str):
        """Parse column definition"""
        # Extract column name
        match = re.match(r'`?([^`\s]+)`?\s+(.+)', definition.strip())
        if not match:
            return
            
        column_name = match.group(1)
        column_spec = match.group(2)
        
        column = ColumnDefinition(name=column_name, data_type='')
        
        # Parse data type
        type_match = re.match(r'(\w+)(?:\(([^)]+)\))?\s*(.*)', column_spec)
        if type_match:
            base_type = type_match.group(1).upper()
            type_params = type_match.group(2)
            remaining_spec = type_match.group(3)
            
            column.data_type = base_type
            
            # Parse type parameters
            if type_params:
                if ',' in type_params:
                    params = [p.strip() for p in type_params.split(',')]
                    column.precision = params[0]
                    if len(params) > 1:
                        column.scale = params[1]
                else:
                    column.length = type_params
            
            # Parse remaining specifications
            remaining_spec = remaining_spec.upper()
            
            # Check for UNSIGNED (affects data type mapping)
            if 'UNSIGNED' in remaining_spec:
                if base_type in ['TINYINT', 'SMALLINT', 'MEDIUMINT', 'INT', 'BIGINT']:
                    # For unsigned integers, we might need to use a larger type
                    pass
            
            # Check for NULL/NOT NULL
            if 'NOT NULL' in remaining_spec:
                column.nullable = False
            elif 'NULL' in remaining_spec:
                column.nullable = True
            
            # Check for AUTO_INCREMENT
            if 'AUTO_INCREMENT' in remaining_spec:
                column.auto_increment = True
            
            # Extract default value
            default_match = re.search(r'DEFAULT\s+([^,\s]+(?:\([^)]*\))?)', remaining_spec)
            if default_match:
                column.default_value = default_match.group(1)
            
            # Extract comment
            comment_match = re.search(r'COMMENT\s+[\'"]([^\'"]*)[\'"]', remaining_spec)
            if comment_match:
                column.comment = comment_match.group(1)
            
            # Extract charset and collation
            charset_match = re.search(r'CHARACTER\s+SET\s+(\w+)', remaining_spec)
            if charset_match:
                column.charset = charset_match.group(1)
            
            collation_match = re.search(r'COLLATE\s+([^\s,]+)', remaining_spec)
            if collation_match:
                column.collation = collation_match.group(1)
        
        table.columns.append(column)
    
    def parse_primary_key(self, table: TableDefinition, definition: str):
        """Parse primary key definition"""
        match = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', definition, re.IGNORECASE)
        if match:
            columns = [col.strip(' `') for col in match.group(1).split(',')]
            index = IndexDefinition(name='PK_' + table.name, type='PRIMARY', columns=columns)
            table.indexes.append(index)
    
    def parse_unique_key(self, table: TableDefinition, definition: str):
        """Parse unique key definition"""
        # UNIQUE [INDEX|KEY] [index_name] (col_list)
        match = re.search(r'UNIQUE\s+(?:(?:INDEX|KEY)\s+)?(?:`?([^`\s]+)`?\s+)?\(([^)]+)\)', definition, re.IGNORECASE)
        if match:
            index_name = match.group(1) or f'UQ_{table.name}'
            columns = [col.strip(' `') for col in match.group(2).split(',')]
            index = IndexDefinition(name=index_name, type='UNIQUE', columns=columns)
            table.indexes.append(index)
    
    def parse_index(self, table: TableDefinition, definition: str):
        """Parse regular index definition"""
        # [INDEX|KEY] [index_name] (col_list)
        match = re.search(r'(?:INDEX|KEY)\s+(?:`?([^`\s]+)`?\s+)?\(([^)]+)\)', definition, re.IGNORECASE)
        if match:
            index_name = match.group(1) or f'IX_{table.name}'
            columns = [col.strip(' `') for col in match.group(2).split(',')]
            index = IndexDefinition(name=index_name, type='INDEX', columns=columns)
            table.indexes.append(index)
    
    def parse_fulltext_index(self, table: TableDefinition, definition: str):
        """Parse fulltext index definition"""
        match = re.search(r'FULLTEXT\s+(?:INDEX|KEY)?\s*(?:`?([^`\s]+)`?\s+)?\(([^)]+)\)', definition, re.IGNORECASE)
        if match:
            index_name = match.group(1) or f'FT_{table.name}'
            columns = [col.strip(' `') for col in match.group(2).split(',')]
            index = IndexDefinition(name=index_name, type='FULLTEXT', columns=columns)
            table.indexes.append(index)
    
    def parse_spatial_index(self, table: TableDefinition, definition: str):
        """Parse spatial index definition"""
        match = re.search(r'SPATIAL\s+(?:INDEX|KEY)?\s*(?:`?([^`\s]+)`?\s+)?\(([^)]+)\)', definition, re.IGNORECASE)
        if match:
            index_name = match.group(1) or f'SI_{table.name}'
            columns = [col.strip(' `') for col in match.group(2).split(',')]
            index = IndexDefinition(name=index_name, type='SPATIAL', columns=columns)
            table.indexes.append(index)
    
    def parse_constraint(self, table: TableDefinition, definition: str):
        """Parse foreign key and other constraints"""
        # CONSTRAINT [constraint_name] FOREIGN KEY (col_list) REFERENCES table (col_list)
        fk_match = re.search(r'(?:CONSTRAINT\s+`?([^`\s]+)`?\s+)?FOREIGN\s+KEY\s+\(([^)]+)\)\s+REFERENCES\s+`?([^`\s]+)`?\s+\(([^)]+)\)(?:\s+ON\s+DELETE\s+(\w+))?(?:\s+ON\s+UPDATE\s+(\w+))?', definition, re.IGNORECASE)
        
        if fk_match:
            constraint_name = fk_match.group(1) or f'FK_{table.name}'
            columns = [col.strip(' `') for col in fk_match.group(2).split(',')]
            ref_table = fk_match.group(3)
            ref_columns = [col.strip(' `') for col in fk_match.group(4).split(',')]
            on_delete = fk_match.group(5)
            on_update = fk_match.group(6)
            
            constraint = ConstraintDefinition(
                name=constraint_name,
                type='FOREIGN KEY',
                columns=columns,
                reference_table=ref_table,
                reference_columns=ref_columns,
                on_delete=on_delete,
                on_update=on_update
            )
            table.constraints.append(constraint)
    
    def parse_check_constraint(self, table: TableDefinition, definition: str):
        """Parse check constraint definition"""
        match = re.search(r'(?:CONSTRAINT\s+`?([^`\s]+)`?\s+)?CHECK\s+\((.+)\)', definition, re.IGNORECASE)
        if match:
            constraint_name = match.group(1) or f'CK_{table.name}'
            check_condition = match.group(2)
            
            constraint = ConstraintDefinition(
                name=constraint_name,
                type='CHECK',
                check_condition=check_condition
            )
            table.constraints.append(constraint)
    
    def generate_mssql_schema(self, tables: List[TableDefinition]) -> str:
        """Generate MS SQL Server schema from parsed tables"""
        schema_parts = []
        
        # Add header comment
        schema_parts.append("-- MySQL to MS SQL Server Schema Conversion")
        schema_parts.append("-- Generated using automated conversion tool")
        schema_parts.append("-- Please review and test before using in production")
        schema_parts.append("")
        
        # Generate tables
        for table in tables:
            table_sql = self.generate_table_sql(table)
            schema_parts.append(table_sql)
            schema_parts.append("")
        
        # Generate foreign key constraints (after all tables are created)
        for table in tables:
            fk_sql = self.generate_foreign_keys_sql(table)
            if fk_sql:
                schema_parts.append(fk_sql)
                schema_parts.append("")
        
        return "\n".join(schema_parts)
    
    def generate_table_sql(self, table: TableDefinition) -> str:
        """Generate CREATE TABLE statement for MS SQL Server"""
        # Store current table reference for column generation
        self._current_table = table
        
        parts = []
        parts.append(f"CREATE TABLE [{table.name}] (")
        
        # Generate columns
        column_definitions = []
        for column in table.columns:
            col_def = self.generate_column_sql(column)
            column_definitions.append(f"    {col_def}")
        
        # Add primary key inline if it exists
        primary_key = next((idx for idx in table.indexes if idx.type == 'PRIMARY'), None)
        if primary_key:
            pk_columns = ', '.join(f"[{col}]" for col in primary_key.columns)
            column_definitions.append(f"    CONSTRAINT [PK_{table.name}] PRIMARY KEY ({pk_columns})")
        
        # Add check constraints inline
        for constraint in table.constraints:
            if constraint.type == 'CHECK':
                column_definitions.append(f"    CONSTRAINT [{constraint.name}] CHECK ({constraint.check_condition})")
        
        parts.append(",\n".join(column_definitions))
        parts.append(");")
        
        result = "\n".join(parts)
        
        # Add table comment if exists
        if table.comment:
            result += f"\n\n-- Table comment: {table.comment}"
        
        # Add AUTO_INCREMENT note if exists
        if table.auto_increment:
            result += f"\n-- Original MySQL AUTO_INCREMENT start value: {table.auto_increment}"
        
        # Generate indexes (except primary key which is already created)
        for index in table.indexes:
            if index.type != 'PRIMARY':
                index_sql = self.generate_index_sql(table.name, index)
                if index_sql:
                    result += f"\n{index_sql}"
        
        # Clean up reference
        self._current_table = None
        
        return result
    
    def generate_column_sql(self, column: ColumnDefinition) -> str:
        """Generate column definition for MS SQL Server"""
        parts = [f"[{column.name}]"]
        
        # Convert data type
        mssql_type = self.convert_data_type(column)
        parts.append(mssql_type)
        
        # Add IDENTITY for auto increment
        if column.auto_increment:
            # Check if table has AUTO_INCREMENT start value
            table = getattr(self, '_current_table', None)
            if table and table.auto_increment:
                parts.append(f"IDENTITY({table.auto_increment},1)")
            else:
                parts.append("IDENTITY(1,1)")
        
        # Add NULL/NOT NULL
        if not column.nullable:
            parts.append("NOT NULL")
        else:
            parts.append("NULL")
        
        # Add default value
        if column.default_value:
            default_val = self.convert_default_value(column.default_value, column.data_type)
            parts.append(f"DEFAULT {default_val}")
        
        result = " ".join(parts)
        
        # Add column comment as extended property (commented out for now)
        if column.comment:
            result += f" -- {column.comment}"
        
        return result
    
    def convert_data_type(self, column: ColumnDefinition) -> str:
        """Convert MySQL data type to MS SQL Server data type"""
        mysql_type = column.data_type.upper()
        
        if mysql_type not in self.datatype_mapping:
            # Default fallback
            mssql_type = 'VARCHAR(255)'
        else:
            mssql_type = self.datatype_mapping[mysql_type]
        
        # Handle special cases with length/precision
        if mysql_type in ['VARCHAR', 'CHAR', 'BINARY', 'VARBINARY']:
            if column.length:
                length = column.length
                # Convert MySQL's larger varchar to NVARCHAR(MAX) if needed
                if mysql_type == 'VARCHAR' and length.isdigit() and int(length) > 8000:
                    mssql_type = 'NVARCHAR(MAX)'
                else:
                    mssql_type = f"{mssql_type}({length})"
            else:
                # Default lengths
                if mysql_type in ['VARCHAR', 'CHAR']:
                    mssql_type = f"{mssql_type}(255)"
                elif mysql_type in ['BINARY', 'VARBINARY']:
                    mssql_type = f"{mssql_type}(255)"
        
        elif mysql_type in ['DECIMAL', 'NUMERIC']:
            if column.precision and column.scale:
                mssql_type = f"{mssql_type}({column.precision},{column.scale})"
            elif column.precision:
                mssql_type = f"{mssql_type}({column.precision})"
        
        elif mysql_type == 'FLOAT':
            if column.precision:
                # MySQL FLOAT(p) where p <= 24 becomes REAL, p > 24 becomes FLOAT
                if column.precision.isdigit() and int(column.precision) <= 24:
                    mssql_type = 'REAL'
                else:
                    mssql_type = 'FLOAT'
        
        elif mysql_type == 'ENUM':
            # Convert ENUM to VARCHAR with CHECK constraint
            if column.length:
                # Parse enum values: ENUM('value1','value2',...)
                enum_values = column.length
                # Extract the largest value to determine varchar length
                import re
                values = re.findall(r"'([^']*)'", enum_values)
                max_len = max(len(v) for v in values) if values else 50
                mssql_type = f"VARCHAR({max_len})"
            else:
                mssql_type = "VARCHAR(255)"
        
        elif mysql_type == 'SET':
            # Convert SET to VARCHAR
            if column.length:
                # Estimate length needed for SET values
                import re
                values = re.findall(r"'([^']*)'", column.length)
                # SET can contain multiple values separated by commas
                estimated_len = sum(len(v) for v in values) + len(values) - 1 if values else 255
                mssql_type = f"VARCHAR({min(estimated_len, 8000)})"
            else:
                mssql_type = "VARCHAR(8000)"
        
        return mssql_type
    
    def convert_default_value(self, default_value: str, data_type: str) -> str:
        """Convert MySQL default value to MS SQL Server format"""
        default_upper = default_value.upper()
        
        # Handle MySQL specific functions
        if default_upper == 'CURRENT_TIMESTAMP':
            return 'GETDATE()'
        elif default_upper == 'NOW()':
            return 'GETDATE()'
        elif default_upper in ['CURRENT_DATE', 'CURDATE()']:
            return 'CAST(GETDATE() AS DATE)'
        elif default_upper in ['CURRENT_TIME', 'CURTIME()']:
            return 'CAST(GETDATE() AS TIME)'
        elif default_upper == 'NULL':
            return 'NULL'
        elif default_value.startswith("'") and default_value.endswith("'"):
            return default_value
        elif default_value.isdigit() or re.match(r'^-?\d+(\.\d+)?$', default_value):
            return default_value
        else:
            # Wrap in quotes if not already quoted
            return f"'{default_value}'"
    
    def generate_index_sql(self, table_name: str, index: IndexDefinition) -> str:
        """Generate index creation SQL for MS SQL Server"""
        if index.type == 'UNIQUE':
            index_type = 'UNIQUE'
        elif index.type == 'FULLTEXT':
            # Fulltext indexes need special handling in SQL Server
            columns = ', '.join(f"[{col}]" for col in index.columns)
            return f"CREATE FULLTEXT INDEX ON [{table_name}] ({columns}) KEY INDEX [PK_{table_name}];"
        elif index.type == 'SPATIAL':
            # Spatial indexes need special handling
            columns = ', '.join(f"[{col}]" for col in index.columns)
            return f"CREATE SPATIAL INDEX [{index.name}] ON [{table_name}] ({columns});"
        else:
            index_type = ''
        
        columns = ', '.join(f"[{col}]" for col in index.columns)
        return f"CREATE {index_type} INDEX [{index.name}] ON [{table_name}] ({columns});"
    
    def generate_foreign_keys_sql(self, table: TableDefinition) -> str:
        """Generate foreign key constraints SQL"""
        fk_statements = []
        
        for constraint in table.constraints:
            if constraint.type == 'FOREIGN KEY':
                columns = ', '.join(f"[{col}]" for col in constraint.columns)
                ref_columns = ', '.join(f"[{col}]" for col in constraint.reference_columns)
                
                fk_sql = f"ALTER TABLE [{table.name}] ADD CONSTRAINT [{constraint.name}] "
                fk_sql += f"FOREIGN KEY ({columns}) REFERENCES [{constraint.reference_table}] ({ref_columns})"
                
                if constraint.on_delete:
                    if constraint.on_delete.upper() == 'RESTRICT':
                        fk_sql += " ON DELETE NO ACTION"
                    else:
                        fk_sql += f" ON DELETE {constraint.on_delete.upper()}"
                
                if constraint.on_update:
                    if constraint.on_update.upper() == 'RESTRICT':
                        fk_sql += " ON UPDATE NO ACTION"
                    else:
                        fk_sql += f" ON UPDATE {constraint.on_update.upper()}"
                
                fk_sql += ";"
                fk_statements.append(fk_sql)
        
        return "\n".join(fk_statements) if fk_statements else ""

# Example usage and test function
def main():
    """Example usage of the MySQL to MS SQL converter"""
    
    # Test table with AUTO_INCREMENT start value
    table_with_auto_increment = """
    CREATE TABLE `test_table` (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `name` varchar(50) NOT NULL,
      PRIMARY KEY (`id`)
    ) ENGINE=InnoDB AUTO_INCREMENT=6923 DEFAULT CHARSET=utf8mb4
    """
    
    print("Testing table with AUTO_INCREMENT=6923:")
    print("=" * 45)
    converter = MySQLToMSSQLConverter()
    result = converter.convert_schema(table_with_auto_increment)
    print(result)
    print("\n" + "="*50 + "\n")
    
    # Simple test case first
    simple_table = """
    CREATE TABLE users (
      id int NOT NULL AUTO_INCREMENT,
      name varchar(50) NOT NULL,
      PRIMARY KEY (id)
    )
    """
    
    print("Testing simple table:")
    print("=" * 30)
    result2 = converter.convert_schema(simple_table)
    print(result2)

def convert_single_table(mysql_table_schema: str) -> str:
    """Convenience function for converting single table schema"""
    converter = MySQLToMSSQLConverter()
    return converter.convert_schema(mysql_table_schema)

if __name__ == "__main__":
    main()
