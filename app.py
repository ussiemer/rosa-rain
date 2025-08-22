import pandas as pd
import glob
import os
import re
from quart import Quart, request, jsonify, render_template, send_from_directory
import graphene
import asyncio


df = None
schema = None

def load_all_csvs(folder_path: str) -> pd.DataFrame:
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    print("Loading CSV files:", all_files)
    df_list = []

    # Function to convert a string to camelCase
    def to_camel_case(s):
        parts = s.split('_')
        return parts[0] + ''.join(word.capitalize() for word in parts[1:])

    for file in all_files:
        try:
            # Load with two-row header
            temp_df = pd.read_csv(file, header=[0, 1])

            # Combine header levels into a single string
            temp_df.columns = [
                '_'.join([str(c).replace(' ', '').replace('%', 'Prozent').replace('-', '').replace('/', '') for c in col if c])
                for col in temp_df.columns.values
            ]

            # Sanitize and convert to camelCase
            temp_df.columns = [to_camel_case(re.sub(r'[^_a-zA-Z0-9]', '_', col)) for col in temp_df.columns]

            # Add the source file column and convert it to camelCase as well
            temp_df['sourceFile'] = os.path.basename(file)

            df_list.append(temp_df)
        except Exception as e:
            print(f"Error reading and processing file {file}: {e}")

    if not df_list:
        return pd.DataFrame()

    df = pd.concat(df_list, ignore_index=True)
    print("DataFrame loaded with columns:", df.columns.tolist())
    return df

def create_graphql_type(df: pd.DataFrame) -> graphene.ObjectType:
    # A defensive check to ensure columns exist
    if df.empty or not len(df.columns):
        print("DataFrame is empty, cannot create GraphQL type.")
        class CsvType(graphene.ObjectType):
            placeholder = graphene.String()
        return CsvType

    # Dynamically create a GraphQL type
    attrs = {}
    for col in df.columns:
        # Special case for the primary key/label column
        if col == 'Merkmal_Unnamed_0_level_1':
            attrs[col] = graphene.Field(graphene.String)
            continue

        col_type = graphene.String

        # Check for numeric types
        try:
            if pd.api.types.is_float_dtype(df[col]):
                col_type = graphene.Float
            elif pd.api.types.is_integer_dtype(df[col]):
                col_type = graphene.Int
        except TypeError:
            # Fallback to string if type check fails
            pass

        attrs[col] = graphene.Field(col_type)

    return type('CsvType', (graphene.ObjectType,), attrs)

def create_schema_from_df(df: pd.DataFrame):
    global schema
    print("DataFrame columns before schema creation:", df.columns.tolist())
    print("DataFrame head:\n", df.head())
    if df.empty or not len(df.columns):
        print("DataFrame is empty or has no columns, using EmptyQuery.")
        class EmptyQuery(graphene.ObjectType):
            hello = graphene.String()
            def resolve_hello(self, info):
                return "Hello, the database is empty or malformed!"
        schema = graphene.Schema(query=EmptyQuery)
        return
    CsvType = create_graphql_type(df)

    class Query(graphene.ObjectType):
        allData = graphene.List(
            CsvType,
            **{col: graphene.String(description=f"Filter by {col}") for col in df.columns}
        )
        async def resolve_allData(self, info, **kwargs):
            await asyncio.sleep(0.01)
            results = df.copy()
            for key, value in kwargs.items():
                if key in results.columns and value is not None and value != '':
                    results = results[results[key].astype(str).str.contains(value, case=False, na=False)]

            records = results.to_dict('records')

            # Ensure the result is always a list, even for a single record.
            if isinstance(records, dict):
                return [records]

            return records
    schema = graphene.Schema(query=Query)

app = Quart(__name__)

@app.before_serving
async def startup():
    global df, schema
    df = await asyncio.to_thread(load_all_csvs, 'results')
    create_schema_from_df(df)
    print("GraphQL schema created successfully!")
    print("Final DataFrame Columns:", df.columns.tolist())
    print("You can query with these exact field names:")
    for col in df.columns:
        print(f"    {col}")

@app.route("/")
async def index():
    return await render_template('index.html')

@app.route("/graphql", methods=["POST"])
async def graphql_endpoint():
    if schema is None:
        return jsonify({"errors": [{"message": "API not initialized."}]}), 500
    try:
        data = await request.get_json()
        query = data.get("query")
        variables = data.get("variables")

        # Use schema.execute_async for asynchronous resolvers
        result = await schema.execute_async(query, variable_values=variables)

        response = {}
        if result.errors:
            response["errors"] = [{"message": str(e)} for e in result.errors]
        if result.data:
            response["data"] = result.data
        return jsonify(response)
    except Exception as e:
        print(f"GraphQL error: {e}")
        return jsonify({"errors": [{"message": str(e)}]}), 400

@app.route("/static/<path:filename>")
async def static_files(filename):
    return await send_from_directory('static', filename)

if __name__ == "__main__":
    app.run(debug=False)
