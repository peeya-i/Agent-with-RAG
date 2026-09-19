# Agent With RAG Specification
Build a web app to manage an AI Agent with RAG ability.

## 📂 Directory Architecture
The layout isolates domain procedural logic into standard structural boundaries:
```
Agent-with-RAG/
├── database/
├── samle_docs/
├── services/
├── skills/
│   ├── time-weather-skill/
│   │   ├── SKILL.md            # Metadata & SOP for Skill 1
│   │   └── scripts/
│   │       └── env_tools.py    # Public Open-Meteo & Time logic (No Keys Req.)
│   ├── person-information-skill/
│   │   ├── SKILL.md            # Metadata & SOP for Skill 2
│   │   └── data/
│   │       └── registry.csv    # Flat-file database for record resolution
│   └── stock-market-skill/
│       ├── SKILL.md            # Metadata & SOP for Skill 3
│       └── scripts/
│           └── stock_search.py   # Stock search tool
├── tests/                      # Store test files
├── app.py                      # Core Orchestrator
├── config.py                   # Configurable parameters
└── requirements.txt            # Package declarations
```

## GUI
The App should have 4 pages switchable with the tabs or buttons at the top of the window.
  - If the static/images folder has a file called tab-icon.gif, use it as the icon for the tab.
  - If the static/images folder has a file called app-icon.gif, put it on the left side of the App name at the top left of the window.
  - Add icon to the left of each tabs, cards and box names appropriate to the names.
  - At the same level as the tabs on the right side of the screen, put a button in the light red color “Shutdown” button.
    - When the user clicks this button, open a dialog box warning the user that this will shutdown the app and all the services. All the users will be affected by this action. Confirm by typing “Shutdown the service” in the text box.
    - Show two buttons in the dialog box: Cancel, and Confirm. The confirm box should be disabled until the user typed the exact word in the text box.
    - When the user click “Confirm” shutdown all the services started by the app. If some of the supporting services were running before the app started, do not shut them down.
  - To the left of the “Shutdown” button add a status box that shows the status of the backend Agent.
    - Periodically check the Agent API’s health and display the status of all the services needed to support the Agent.
  
  ### First Page: "Chat & Knowledge Synthesis"
    - At the same level as the page title at the right side of the screen, put a drop down box showing the currently selected model.
      - Check Google AI Studio for the active models that are capable of synthesizing and outputting text then list them in the dropdown.
      - Include the option to select a Custom model. When the Custom model is selected, show a text box for the user to enter the API Endpoint of the model. The default text should be the last endpoint entered. If none exists, put “http://127.0.0.1:8000/v1/chat/completions”.
      - To the left of the model choice dropdown, add a box to allow the user to select the “Temperature” parameter to send to the model.
      - To the left of the temperature box, add a text box to allow the user to set the “Max Tokens” parameter to send to the model. Do not allow the user to set the number larger than the max tokens of the model selected.
    
    #### Left Card: "Chat with the Agent"
      - Add a drop down box called "Agent" on the right side of the card. The choices are: Custom Agent, Google ADK LlmAgent.
        - If the user selects Custom Agent, use the agent described in the Agent section of this document.
        - If the user selects Google ADK Agent, use the google adk agent
      - To the right of the "Agent" box, add a text box for the user to select the "Max Turns" the default is 3. Do not allow the user to set the number larger than 10. This is the maximum number of turns for the Agent.
      - In the next row, add a dropbox called "Skill Selector" to allow the user to select the skills the agent can use.
        - First option in the dropbox should be "Vector Store Selects" (default option). The Custom Agent will query the skills vector store to select the skills to use in the prompt to the model.
        - The second option should be "LLM Selects". The Custom Agent will ask the LLM to select the skills to use in the prompt to the model.
        - The remainder of the selection should be the list of skills in skills/ folder. The Custom Agent will use the skills selected in the prompt to the model.
      - In the same row as "Skill Selector", add a dropbox to allow the user to select the maximum number of RAG chunks to send to the model. Default value is 5.
      - Add a text box "Threshold" for the user to enter the threshold to use for the vector store query. The default value is 0.2. 
      - At the bottom of the card, put a text box for the user to enter the chat message.
        - Use a new conversation ID for each question
        - When the user clicks on the "Send" button or presses the Enter key, the agent will process the message.
      - Use the typical chat user interface to display the chat messages and the agent's responses.
      - Once the response is completed, display the response.
        - Add the detail box in the response with a button named “Show Logs”. Within the detail box, add bubbles showing the name of the components that generated the logs (such as Agent, Tools, RAG, Skills), icons appropriate for the components, and the elapse time of each step.
        - When the user clicks on the "Show Logs" button, the detail box should expand to show the full content of the step including the logs. Use scroll area in the bubble if the content is too long.
        - Make the "Show Logs" button toggle between expand and collapse.
        - Anchor "Show Logs" button at the top-right coner of the detail box.

    #### Right Card: "Retrieved Context Evidence"
      - Add a box "Doc Threshold" for the user to set the threshold for the document retrieval. The default value is 0.3.
      - Display the contents of the information retrieved from the vector store.
        - Include results from the skills vector store and the documents vector store.
        - Group the results by the documents
      - Allow the user to scroll through the data

  ### The second page: “Vector DB Ingestion”
    - At the same level as the page title at the right side of the page, put the statistics of the ingestion. Display the number of chunks, documents ingested, and the size of the DB in MByte.
    - To the left of the statistic, add a button to “Update Skills Database”. When the button is selected, scan the skills/ folder and load new skills that are not in the skill database. Skills already in the database should not be loaded
    - To the left of the “Update Skills Database”, add a dropbox showing the list of Embedder that ollama can download.
      - Display the currently running model.
      - If the user selects a different model, display a pop up window with a stern warning to the user that changing the model will delete all the data currently in the database.
        - Show two buttons: Cancel and Delete Data (initially disabled).
        - Ask the user to type the text to confirm they want to change the model.
        - When the user typed the exact text, enable the “Delete Data” button.
        - When the user clicks “Delete Data”, proceed to delete the data in the document and skill databases, then make ollama to load the new model selected.
        - After the ollama completes updating the model, scan the skills/ folder and import the skills to the skill database
    
    #### Left Card: "Populate Vector Database"
    - Takes a url or local directory, then creates a private vector database from documents in the url or local directory and saves it to the database/ folder.
      - Provide 5 buttons for the user to click with samples of web URL that can be imported into the database.
      - Add a sub card called “Advanced Chunking Parameters” to allow the user to select the Chunk size and Overlap in the number of characters. The sub card should be collapsed by default.
      - Add the button at the bottom to populate vector database
      - When loading the database, make sure there is no duplicated chunk
      - The card should be half of the page width

    #### Right Card: “Vector Storage Status”.
      - At the right side of the box put a button to allow the user to Reset the DB.
      - The card should show if the ingestion is in progress
      - It should also list the name of the document ingested and the number of chunks created and the total number of characters
      - Allow the user to scroll through the list of ingested documents
      - Allow the user to delete any document from the DB by using the Delete button on the right side of the document row
      - The card should be half of the page width

    #### Bottom: "Available Embedding Models".
    - Display the list of available Embedding Models for the embedding service. Briefly list the characteristics including the dimensions, context window, size, brief description, and status (Installed, Active, Available to Pull).

  ### The third page: “Telemetry”
    - On the right side of the page, put the button called “Refresh Telemetry” to allow the user to manually refresh the page.
    - To the left of the “Refresh Telemetry” button, add a dropdown box to list the models that had been used. Filter the contents of the telemetry page based on the model selected. Include “All Models” as the default option.
    - Next, shows Total Prompts, Total Response, Total Errors, Total Input Tokens, and Total Output Tokens sent to and received from the LLM models.
    #### Top Card: "System Throughput & Token Velocity"
    - Below the statistic, add a card that shows 2 graphs.
      - At the top of the box, there is a dropdown that selects the Aggregation/Refresh Interval with choices: 1 min, 15 min (default), 1 hr, and 1 day.
      - The second dropdown to the right allows the user to select the time range with options for: Last hr, 1 day (default), Week, Month and Custom. When Custom is selected, bring up two boxes with a dropdown calendar that allows the user to select the starting date and ending date.
      - Below the selection, the Left plot shows the line graphs of the number of prompts, responses and errors per Interval selected. The X-axis shows the time range selected.
      - The right plot shows the line graph of the number of input and output tokens per Interval selected. The X-axis shows the time range selected.
    #### Bottom Card: “Other Important Statistic not Available for Low-Performance Computer”
      - Time to First Token (TTFT): The duration between a user sending a prompt and receiving the very first token. This is the most critical metric for perceived speed in streaming applications.
      - Inter-Token Latency (ITL): The average time elapsed between generating each subsequent token.
      - Tokens Per Second (TPS): The throughput speed of the model generation (often measured per request or aggregated across the server).
      - Time Per Output Token (TPOT): The total time taken to generate the response divided by the number of output tokens.

  ### The fourth page: “Audit Log & Event”
    - To the right side of the page, add a button called “Refresh” to allow the user to manually refresh the page.
    - To the left of the “Refresh” button, add a button to allow the user to clear the logs. This will delete all the logs. When the user clicks on this box, open a pop up window asking the user to confirm.
    - Next, display the statistics of the total user prompts logged, model calls, Ollama embeds, Avg call latency.
    #### Top table: "User Conversations (Select a row to inspect associated events)"
      - Display the list of all the user conversations in the log. Display the timestamp (in local time), conversation ID, User Query, Agent Response, Agent Type, Number of Events (occured during the conversation), etc.
      - Display at most 7 items and allow the user to scroll through all the items.
      - When the user click on a row, the next table should be populated with the logs associated with the conversation selected.
      - The selected row should be highlighted.
    #### Bottom table: "Events for Conversation for <Conversation ID>
    - Display the logs associated with the conversation selected in the table above. The table should have columns showing:
      - Time and Date (local time)
      - Event Type
      - Invoker
      - Target
      - Short Description
    - When the row is clicked, open a pop up window to show all the detailed logs including the JSON payload in human readable format
      - The popup window should show the text in the prompt and the response in a human readable format. If the text is JSON, display it in a JSON viewer format.

## Requirements
- Import API key and all the contents from the .env file
- Use the PORT defined in the .env file for the default port of the app.
  - If no PORT is defined in the .env file, use 5000 as the default port.
  - The port can be overridden by passing the --port argument to the app.
- Use the GEMINI_MODEL from .env file as the default LLM model for the Agent. If the model name is not defined in the .env file, set GEMINI_MODEL=gemma-4-26b-a4b-it as the default LLM model to use. The actual model used should be the one selected in the dropdown menu in the Chat page.
- All of the backend code should be written in python, the web app should be built using flask.
- All calls to external resources like Google AI Studio or any external API should be done from the backend python code, not from the frontend.
- Use local ollama to vectorize the text.
- Use chromadb for vector store
- Upon start up, the app should check whether ollama is currently running and start the service if it is not already started.
- When the app terminates, shutdown the ollama service if the app started the service. If it is already running when the app starts, do not shutdown ollama.
- On start up, get the list of ONLY active LLM models for text generation from Google AI Studio API that can be used by the Agent. Use the list in the dropdown menu in the Chat page.
- Set DEFAULT_LLM_MODEL=gemma-4-26b-a4b-it in config.py as the default LLM model to use. Use this constant as the default everywhere the model is used.

- The skills should have a separate skill vector database and be built as follow:
  - The contents from name and description fields should be sent to the Embedder/Vectorizer.
  - The vectors and the complete text of the SKILL.md file should be stored in the database as one record.
  - Upon start up, the app should scan the skills/ folder and load the skills that are not currently in the skills vector database.
  - When the skill vector database is queried, the list of skills that have scores higher than minimum threshold from the UI should be returned.

  ### The Custom Agent
  The Custom Agent should operate as follow:
    - Set the agent_type to "Custom Agent" and add it to the log record when an agent is invoked.
    - When it receives the message from the user, query the Skills vector store to find the skills that have higher matching score than the minimum threshold set by the user.
    - If no skill is found, send the user query to the LLM using the simple system prompt as an assistant to answer the question.
    - If there are multiple skills found, send the user message and the 2 highest matching skills to the LLM to get the instruction or plan for the tool execution.
      - The system prompt should ask the LLM to determine if any of the tools should be invoked to gather more information to answer the question.
      - The system prompt should ask the LLM to respond with JSON format indicating the tool to be executed and the arguments to be passed to the tool.
      For example:
        {
          "tool": "person_search.query_person_registry",
          "arguments": {
            "keyword": "Lucas Dubois",
            "field": "name",
            }
          }
    - If the LLM determines that a procedural tool should be executed, execute the tool to obtain the needed information. Send a prompt to the LLM with the results from the tool. Repeat until the the final answer is received. Limit the number of loops no more than MAX_LLM_TURNS.
    - Minimize skill-specific code in the orchestrator
    - The last llm call should use typical system prompt as an assistant to answer the question. The final output of the agent is the response from this last LLM call.
    - Only perform vector search for documents when the skill search result and the model direct the Agent to perform the search.
    - Minimize the number of loops to obtain the final answer. The maximum number of loops should be Max turns configured in the GUI.
    - Format the final output to make it easy for human reading and understanding.

  ### Google ADK Agent
    - Create a python code in services/ folder to use LlmAgent from Google ADK.
    - Use the model selected in the Chat & Knowledge Synthesis page.
    - Set the agent_type to "Google ADK Agent" and add it to the log record.
    - Use the skills and tools available in skills/ folder.
    - Create logs for all the invocations and responses when the Agent is invoked.
      - Include all the details needed to show in the Audit Log & Event page.
      - Create logs when the Agent invoke and receive response from the model. Include the actual payload.

## Sample Skills and Tools
- Create the following skills using the folder structure in the Directory Architecture. The skills should at least have the name, description, Trigger Queries, etc:
  - Get the time and weather of the city from the site that doesn't require API key
  - Get the list of stocks with the highest percentage increase or lowest percentage decrease based on the chat question
  - Get the list of text chunks from the document vector database. Write the SKILL.md file description to indicate that the tool can be used to get the list of text chunks from the document vector database
  - Get the name, city, country, or job title of the person in the CSV file.
    - Create 20 random samples of the CSV file with name, city, country, or job title for the tool to query
  - All the python tool should be in the skills/<skill_name>/scripts/ folder

## Sample Documents
- Create 3 sample documents in the folder called sample_docs/.
  - One document should be about Agent and RAG technology,
  - The second document should be a sample of a company marketing strategy
  - The third document should be a sample of financial report for the company

## Logs
- Create logs for all the invocations and responses between the following components. The log should include the actual details of the payloads passed to and from the components. Store the logs in the database/ folder in log.json file. The log should be in JSON format. Display in the same conversation event.
    - agent - full log of the message sent to the agent and the response received from the agent.
    - skill search - full log of the message sent to the skill search and the response received from the skill search. Include the name of the vectorizer and response from the vectorizer.
    - document search - full log of the message sent to the document search and the response received from the document search.
    - tool - full log of tool message passed to and received from the tools including the actual API payload or parameters in the function call. Do not redact or replace any part of the payload and response.
    - ollama vector - log the first 50 characters of the text chunk sent for embedding. Include the name of the vectorizer and response from the vectorizer. Do not include the vectors.
    - LLM - prompts sent to and response received from the model include the FULL payload. Do not log the API call for model acces. Only log the model invocation and response with the FULL PAYLOAD.
    - In the log, include the time of the call, the type of the call, the invoker, the recipient, and all the raw payload passed in the message.
    - Do not combine the logs of from the request and response into the same log entry when displaying on the screen. Each invocation/response should be a separate entry in the log.
  - Redact API keys with “****” if any is present.

## Misc
- Create a README.md with a brief description about:
  - what this system does
  - how to install the components needed
  - how to start all the services
  - how to shutdown all the services
  - user guide with information on how to use the system

- Create a requirements.txt and put all the libraries used by the app
