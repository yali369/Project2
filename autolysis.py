# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "seaborn",
#   "matplotlib",
#   "requests",
#   "openai"
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
 
# Set global variables
TOKEN_ENV_VAR = "AIPROXY_TOKEN"

if TOKEN_ENV_VAR not in os.environ:
    print(f"Error: Please set the {TOKEN_ENV_VAR} environment variable.")
    sys.exit(1)




def chat_with_model(messages,TOKEN_ENV_VAR,model="gpt-4o-mini"):
    try:
      
        openai.api_key = os.environ[TOKEN_ENV_VAR]
    except ModuleNotFoundError:
        print("Error: The 'openai' module is not installed. Please install it by running 'pip install openai'.")
        sys.exit(1)
    # Define the headers, including authorization
    headers = {
        "Authorization": f"Bearer {openai.api_key}"
    }

    url = "http://aiproxy.sanand.workers.dev/openai/v1/chat/completions" 

    data = {
        "model": model,
        "messages": messages
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()

        reply = response_data['choices'][0]['message']['content']
        return reply
    except requests.exceptions.RequestException as e:
        print("An error occurred:", e)
        return None

def extract_and_execute_functions(llm_response,analysis_prompt, filename, model="gpt-4o-mini"):
    try:
        code_blocks = []
        for block in llm_response.split("```"):
            if block.strip().startswith("python"):
                code_blocks.append(block.strip()[len("python"):].strip())

        if not code_blocks:
            print("No Python code found in LLM response.")
            return None

        code_to_execute = "\n\n".join(code_blocks)

        execution_globals = {}
        execution_output = io.StringIO()

        with contextlib.redirect_stdout(execution_output), contextlib.redirect_stderr(execution_output):
            try:
                exec(code_to_execute, execution_globals)
            except Exception as e:
                execution_output.write(f"Error defining functions: {e}\n")

        results = execution_output.getvalue()
        execution_output.close()

        summarization_prompt = (
            "The following Python functions were executed with the provided filename input. "
            "Summarize the results, include table of content, input data details and provide insights, storylines based on the output:\n\n"
            f"Code:\n{code_to_execute}\n\n"
            f"In the summariz don't keep the python code\n"
            f"Results:\n{results}"
        )

        messages = [
            {"role": "system", "content": "You are an expert data scientist need to give storyline of the analysis."},
            {"role": "user", "content": summarization_prompt},
            {"role": "user", "content": llm_response},
        ]

        summary = chat_with_model(messages,TOKEN_ENV_VAR)
        return summary
    except Exception as e:
        print(f"Error processing the LLM response or executing the code: {e}")
        return None

def analyze_and_visualize(csv_file):
    script_dir = os.getcwd()  # Current working directory
    file_path = os.path.join(script_dir, csv_file)

    try:
        df = pd.read_csv(file_path, encoding="ISO-8859-1")
    except Exception as e:
        print(f"Error loading {csv_file}: {e}")
        sys.exit(1)

    summary = {
        "shape": df.shape,
        "columns": {col: str(df[col].dtype) for col in df.columns},
        "missing_values": df.isnull().sum().to_dict(),
        "example_rows": df.head(3).to_dict(orient="records"),
    }

    numeric_stats = df.select_dtypes(include=['number']).describe().to_dict()
    categorical_stats = df.select_dtypes(include=['object', 'category']).describe().to_dict()
    basic_stats = {**numeric_stats, **categorical_stats}
    
    numeric_df = df.select_dtypes(include=['number'])
    categorical_df = df.select_dtypes(include=['object', 'category'])
    
    
    
    
   #  # Save a histogram for each numeric column in the current working directory
   #  for column in numeric_df.columns:
   #     plt.figure()
   #     sns.histplot(numeric_df[column], kde=True)
   #     plt.title(f"Histogram of {column}")
   #     plt.savefig(os.path.join(script_dir, f"{column}_histogram.png"))
   #     plt.close()

   # # Save a correlation heatmap
   #  if not numeric_df.empty:
   #     plt.figure(figsize=(10, 8))
   #     corr_matrix = numeric_df.corr()
   #     sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt=".2f")
   #     plt.title("Correlation Heatmap")
   #     plt.savefig(os.path.join(script_dir, "correlation_heatmap.png"))
   #     plt.close()
    
    
    

    analysis_prompt = (
    "You are a data analyst. Based on the following dataset details, suggest insights and analyses:\n"
    f"- Dataset: {csv_file}\n"
    f"- Shape: {summary['shape']}\n"
    f"- Columns: {summary['columns']}\n"
    f"- Missing values: {summary['missing_values']}\n"
    f"- Example rows: {summary['example_rows']}\n"
    f"- Save chart location: {script_dir}\n"
    f"- Basic statistics: {basic_stats}\n"
    "Provide Python code snippets for additional analysis if needed depending on data such as outliers,\nsave in the current working directory under folder as input csv file name i.e.'*.csv'.\n"
    "data imputation or handling missing, nan, cleaning data need to be addressed by code \n"
    "Additionally, the file loading must handle encoding issues. Specifically, the CSV file should be loaded as follows:\n"
    "- First, try to load the file using UTF-8 encoding.\n"
    "- If a `UnicodeDecodeError` occurs (meaning UTF-8 encoding failed), fall back to using `ISO-8859-1` (latin1) encoding to successfully load the file.\n"
    "\n"
    f"- save charts in current working directory folder  under folder as input csv file name i.e.'*.csv'(use os.getcwd())\n"
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
        {"role": "user", "content": "save the output of python code in current directory"},
    ]

    llm_response = chat_with_model(messages,TOKEN_ENV_VAR)
    return llm_response,analysis_prompt

import os

def generate_readme(csv_file, llm_response):
    script_dir = os.getcwd()  # Current working directory
    readme_path = os.path.join(script_dir, "README.md")

    readme_content = f"""# Analysis of {csv_file}

## Overview

This analysis was conducted using an automated pipeline. Below are the key insights and visualizations.

## Key Findings

{llm_response}

## Visualizations

The following charts were generated and saved in the current directory:

"""

    for chart in sorted(os.listdir(script_dir)):
        if chart.endswith(".png"):
            readme_content += f"- ![{chart}]({chart})\n"

    with open(readme_path, "w") as readme_file:
        readme_file.write(readme_content)

    print(f"README.md file generated at {readme_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_filename>")
        sys.exit(1)

    csv_file = sys.argv[1]
    llm_response1,analysis_prompt = analyze_and_visualize(csv_file)
    summary = extract_and_execute_functions(llm_response1,analysis_prompt, csv_file, model="gpt-4o-mini")
    generate_readme(csv_file, summary)
