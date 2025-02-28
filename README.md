# TableAgentGPT

Welcome to **TableAgentGPT**! This tool allows you to interact with your tabular data by generating queries and retrieving insights on your behalf.

## Getting Started

To begin using TableAgentGPT, you need to load your data along with its metadata after running `TalkWithYourTable.ipynb` notebook. Use the following command format:

```
/load <file_path> <table_columns_description>
```

### Example:
```
/load sample_data/ds_salaries.csv sample_data/ds_salaries_schema.txt
```

Once your data is loaded, you can ask questions about it, and TableAgentGPT will query the data to provide relevant insights.

## Exiting the System
To exit the system, simply type:
```
/q
```


