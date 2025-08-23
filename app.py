import pandas as pd
import glob
import os
import re
from quart import Quart, request, jsonify, render_template, send_from_directory
import graphene
import asyncio
import traceback

df = None
schema = None

def load_all_csvs(folder_path: str) -> pd.DataFrame:
    all_files = glob.glob(os.path.join(folder_path, "*.csv"))
    print("Loading CSV files:", all_files)
    df_list = []

    for file in all_files:
        try:
            temp_df = pd.read_csv(file, header=[0, 1], sep=';')

            temp_df.columns = [
                '_'.join([str(c) for c in col if c])
                for col in temp_df.columns.values
            ]

            new_cols = []
            for col in temp_df.columns:
                col = re.sub(r'(Erststimmenmore|Zweitstimmenmore)', '', col)
                col = re.sub(r'Gewinn.*', 'Gewinn', col)
                col = re.sub(r'more', '', col)
                col = re.sub(r'^(Erststimmen|Zweitstimmen)\1', r'\1', col)
                col = re.sub(r'Unnamed: 0_level_1', 'Merkmal', col)
                new_cols.append(col)

            temp_df.columns = new_cols

            temp_df.columns = [
                col.replace(' ', '_').replace('__', '_').replace('-', '').replace('%', '')
                for col in temp_df.columns
            ]

            temp_df.rename(columns={'Merkmal_Merkmal': 'Merkmal'}, inplace=True)

            temp_df['sourceFile'] = os.path.basename(file)

            df_list.append(temp_df)
        except Exception as e:
            print(f"Error reading and processing file {file}: {e}")
            traceback.print_exc()

    if not df_list:
        return pd.DataFrame()

    df = pd.concat(df_list, ignore_index=True)
    print("DataFrame loaded with columns:", df.columns.tolist())
    return df

def create_graphql_type(df: pd.DataFrame) -> graphene.ObjectType:
    if df.empty or not len(df.columns):
        print("DataFrame is empty, cannot create GraphQL type.")
        class CsvType(graphene.ObjectType):
            placeholder = graphene.String()
        return CsvType

    attrs = {}
    for col in df.columns:
        if col == 'Merkmal':
            attrs[col] = graphene.Field(graphene.String)
            continue

        col_type = graphene.String

        try:
            if pd.api.types.is_float_dtype(df[col]):
                col_type = graphene.Float
            elif pd.api.types.is_integer_dtype(df[col]):
                col_type = graphene.Int
        except TypeError:
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
