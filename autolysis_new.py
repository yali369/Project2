# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "seaborn",
#   "matplotlib",
#   "requests",
#   "openai",
#   "sklearn"
# ]
# ///

import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import requests
import io
import contextlib
import openai
import ast
import sklearn

# Set global variables
TOKEN_ENV_VAR = "AIPROXY_TOKEN"

if TOKEN_ENV_VAR not in os.environ:
    print(f"Error: Please set the {TOKEN_ENV_VAR} environment variable.")
    sys.exit(1)


def fetch_llm_response(messages, token_env_var, model="gpt-4o-mini"):
    """
    Query a language model API to fetch a response.

    Parameters:
        messages (list): List of message dictionaries for the LLM.
        token_env_var (str): Environment variable containing the API token.
        model (str): The model to use for querying the LLM.

    Returns:
        str: The content of the LLM response.
    """
    openai.api_key = os.environ[token_env_var]
    headers = {"Authorization": f"Bearer {openai.api_key}"}
    url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

    data = {"model": model, "messages": messages}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while querying the LLM: {e}")
        return None


def extract_python_code_blocks(text):
    """
    Extract Python code blocks from a given text.

    Parameters:
        text (str): The input text containing code blocks.

    Returns:
        list: A list of Python code snippets.
    """
    code_blocks = []
    for block in text.split("```"):
        if block.strip().startswith("python"):
            code_blocks.append(block.strip()[len("python"):].strip())
    return code_blocks


def execute_code_snippets(code_blocks):
    """
    Execute a list of Python code snippets and capture their output.

    Parameters:
        code_blocks (list): List of Python code snippets.

    Returns:
        str: Captured execution output.
    """
    execution_globals = {}
    execution_output = io.StringIO()

    with contextlib.redirect_stdout(execution_output), contextlib.redirect_stderr(execution_output):
        for code in code_blocks:
            try:
                exec(code, execution_globals)
            except Exception as e:
                execution_output.write(f"Error executing code: {e}\n")

    result = execution_output.getvalue()
    execution_output.close()
    return result


def process_and_run_code(llm_response, filename):
    """
    Process LLM response to extract and execute Python code, then generate a summary.

    Parameters:
        llm_response (str): The response containing Python code.
        filename (str): Name of the input file for context.

    Returns:
        str: Summarized insights from the code execution.
    """
    code_blocks = extract_python_code_blocks(llm_response)
    if not code_blocks:
        print("No Python code found in LLM response.")
        return None

    execution_results = execute_code_snippets(code_blocks)

    summarization_prompt = (
        "The following Python functions were executed with the provided filename input. "
        "Summarize the results, include table of content, input data details and provide insights, storylines based on the output:\n\n"
        f"Execution Results:\n{execution_results}\n\n"
        "List limitations and suggest future analyses."
    )

    messages = [
        {"role": "system", "content": "You are an expert data scientist."},
        {"role": "user", "content": summarization_prompt},
    ]
    return fetch_llm_response(messages, TOKEN_ENV_VAR)


def load_csv_with_fallback(file_path):
    """
    Load a CSV file with a fallback for encoding issues.

    Parameters:
        file_path (str): Path to the CSV file.

    Returns:
        pd.DataFrame: Loaded DataFrame.
    """
    try:
        return pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding="ISO-8859-1")


def analyze_data(file_path):
    """
    Perform data analysis on the given CSV file.

    Parameters:
        file_path (str): Path to the CSV file.

    Returns:
        tuple: LLM response and analysis prompt.
    """
    try:
        df = load_csv_with_fallback(file_path)
    except Exception as e:
        print(f"Error loading file: {e}")
        sys.exit(1)

    summary = {
        "shape": df.shape,
        "columns": {col: str(df[col].dtype) for col in df.columns},
        "missing_values": df.isnull().sum().to_dict(),
        "example_rows": df.head(3).to_dict(orient="records"),
    }

    numeric_df = df.select_dtypes(include=['number'])

    analysis_prompt = (
     "You are a data analyst. Based on the following dataset details, suggest insights and analyses:\n"
     f"- Dataset: {csv_file}\n"
     f"- Shape: {summary['shape']}\n"
     f"- Columns: {summary['columns']}\n"
     f"- Missing values: {summary['missing_values']}\n"
     f"- Example rows: {summary['example_rows']}\n"
     #f"- Save chart location: {script_dir}\n"
     #f"- Basic statistics: {basic_stats}\n"
     "Provide Python code snippets for additional analysis if needed depending on data such as outliers,\nsave in the current working directory under folder as input csv file name i.e.'*.csv'.\n"
     "data imputation or handling missing, nan, cleaning data need to be addressed by code \n"
     "Additionally, the file loading must handle encoding issues. Specifically, the CSV file should be loaded as follows:\n"
     "- First, try to load the file using UTF-8 encoding.\n"
     "- If a `UnicodeDecodeError` occurs (meaning UTF-8 encoding failed), fall back to using `ISO-8859-1` (latin1) encoding to successfully load the file.\n"
     "\n"
     f"- save charts in current working directory folder  under folder as input csv file name i.e.'*.csv'(use os.getcwd())\n"
     "appropriate labels for the axes on the plots:\n"
     "Ensure the following analyses are conducted on the dataset:\n"
     "Divide dataset as numerical and categorical:\n"
     "- Perform basic statistical analysis on categorical and numerical separtely (mean, median, mode, standard deviation, etc.) on the dataset.\n"
     "- Generate a histogram, lineplot and a box plot to visualize the distribution of key variables.\n"
     "- Compute the on numerical data compute correlation matrix, ensuring that only the int/float columns are used for correlation computation.\n"
     "- on numerical dataset Perform a regression analysis on important variables, and plot the regression line, showing the equation and R-squared value.\n"
     "-do additional analysis of outlier identificaiton, "
     "- save the chart (512x512 px images) with filename without any space in the Current working directory.\n"
     "Provide Python code snippets to perform the analysis and visualization tasks as needed."
     )

    messages = [
        {"role": "system", "content": "You are an expert data scientist."},
        {"role": "user", "content": analysis_prompt},
    ]

    llm_response = fetch_llm_response(messages, TOKEN_ENV_VAR)
    return llm_response, analysis_prompt


def generate_readme(file_path, insights):
    """
    Create a README file summarizing analysis insights.

    Parameters:
        file_path (str): Path to the input CSV file.
        insights (str): Insights generated from the analysis.
    """
    readme_content = f"""# Analysis of {file_path}

## Overview

This analysis was conducted using an automated pipeline. Below are the key insights and visualizations.

## Key Findings

{insights}

## Visualizations

Generated charts are saved in the current directory.
"""
    readme_path = os.path.join(os.getcwd(), "README.md")
    with open(readme_path, "w") as file:
        file.write(readme_content)
    print(f"README.md generated at {readme_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_filename>")
        sys.exit(1)

    csv_file = sys.argv[1]
    llm_response, analysis_prompt = analyze_data(csv_file)
    summary = process_and_run_code(llm_response, csv_file)
    generate_readme(csv_file, summary)
