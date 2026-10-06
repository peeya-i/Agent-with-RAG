# Agent With RAG Specification V2
Build a web app to manage an AI Agent with RAG ability.

## 📂 Directory Architecture
```text
Agent-with-RAG/
├── agents/                  # Custom and Google ADK Agent microservices (Port 8002)
│   ├── custom_agent/        # Custom autonomous planning & orchestrator agent
│   ├── genai/               # Google ADK / GenAI Agent implementation
│   ├── secrets/             # Agent runtime secrets (.env, keys)
│   ├── skills/              # Domain skills (SKILL.md, tools, and trigger queries)
│   ├── Dockerfile
│   └── server.py
├── auth_service/            # Authentication & API Key Management Service (Port 8001)
│   ├── secrets/                # SQLite persistent storage (auth.db)
│   ├── Dockerfile
│   └── server.py
├── doc_RAG/                 # ChromaDB Vector Store & Embedding Manager (Port 8003)
│   ├── chroma/              # Persistent vector store database
│   ├── Dockerfile
│   └── server.py
├── logging/                 # Central Logging & Telemetry Service (Port 8006)
│   ├── logs/                # Persistent JSON event logs (log.json)
│   ├── Dockerfile
│   └── server.py
├── tools/                   # Procedural Tools Service (Port 8005)
│   ├── data/                # Data storage (employee_database.csv)
│   ├── scripts/             # Tool implementation & seeding scripts
│   ├── Dockerfile
│   └── server.py
├── web_ui/                  # Interactive 6-Tab Web Dashboard (Port 8000)
│   ├── secrets/             # User secrets & session keys
│   ├── static/              # CSS, JavaScript, and UI icons
│   ├── templates/           # Flask Jinja2 HTML templates
│   ├── Dockerfile
│   └── app.py
├── sample_docs/             # Sample knowledge documents (Markdown & PDF)
│   ├── agent_and_rag.md     # Agent and RAG architecture overview (~3000 words)
│   ├── company_marketing_strategy.md # Enterprise marketing strategy (~3000 words)
│   ├── financial_report.md  # Multi-year financial performance report (~3000 words)
│   ├── nexus_enterprise_solutions_company_profile.pdf # Extended company profile (>=4000 words)
│   ├── vanguard_global_logistics_company_profile.pdf # Extended company profile (>=4000 words)
│   └── product_catalog_100_offerings.pdf # 100 products with tiered volume pricing (1, 10, 100)
├── scripts/                 # Automation & PDF generation scripts
│   ├── build_all_sample_pdfs.py # Master generator for sample PDF documents
│   ├── nexus_profile_data.py    # Nexus Enterprise profile data generator
│   ├── vanguard_profile_data.py # Vanguard Logistics profile data generator
│   └── product_catalog_data.py  # 100 product offerings catalog data generator
├── tests/                   # Pytest microservices test suite
├── docker-compose.yml       # 7-container deployment configuration
├── requirements.txt         # Root Python dependencies
└── README.md                # System documentation and operational guide
```

## GUI
- Start with the login popup window. Prompt the user to enter their email address and password for Multi-Tenant Access.
  - The login username must be an email address (or `admin` for global administrator).
  - The domain name of the email address is used to determine which RAG documents and tools container CSV databases can be accessed during that login session:
    - `example-a.com`: Test tenant domain authorized to access `example-a.com` RAG documents and `tools/data/employee_database.csv`.
    - `sample-b.com`: Test tenant domain authorized to access `sample-b.com` RAG documents and `tools/data/customer_database.csv`.
    - `admin` (no domain): Global administrator authorized to access ALL RAG documents and BOTH CSV databases.
  - When the user logs in, the authentication service generates and signs a domain-scoped JSON Web Token (JWT) that is used for subsequent authentication across all microservices.
  - Token creation for individual containers (`container_secrets/<container>/keys`) is removed in favor of this login JWT token as the main system-wide authentication.
  - Display two text boxes for entering the email address/username and password.
    - Default test accounts:
      - `admin` / `admin123` (Admin, no domain -> full access to all RAG documents and both CSV files).
      - `user@example-a.com` / `password123` (User, domain `example-a.com` -> access to `example-a.com` documents and `employee_database.csv`).
      - `user@sample-b.com` / `password123` (User, domain `sample-b.com` -> access to `sample-b.com` documents and `customer_database.csv`).
  - Display three buttons: "Create New Account", “Cancel”, and "Ok".
  - If the user clicks “Create New Account”, open a popup window to create a new account:
    - Display two text boxes for entering the email address and password.
    - Display two buttons: "Cancel" and "Add".
    - If the user clicks “Add”, sends the email address and password to the auth service. Accounts are initially created in "Locked" status.
    - If the user clicks “Cancel” button, close the registration window and return to login.
  - If the user clicks “Ok” button, sends the email/username and password to the auth service to validate:
    - If valid, returns signed JWT token with user domain, role, and email claims.
    - If invalid, display an error message "Invalid username or password."
    - If the user has status "Locked", display an error message "Account is Locked. Please contact the administrator."
    - If login succeeds, store the JWT token in the session and proceed to the main console.
  - If the user clicks “Cancel” button, display a message “Thank you for using the app”, close the login window, and exit the app.

### 🛡️ Role-Based Access Control (RBAC) & Multi-Tenant Access Matrix

The system enforces strict role-based access control and tenant isolation across all pages, services, and APIs:

| Role | Scope / Domain | Chat & Telemetry | Log Viewer Access | VectorDB Management | Ingest Documents / Skills | Manage Domain Users | Container Orchestration | API Key Visibility & Management |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **User** | Domain-bound (e.g., `user@example-a.com`) | ✅ Full access | 🔍 View only logs generated by own session | 👁️ View global & own org loaded vectors | ❌ Read-Only (Ingestion disabled) | ❌ No access | ❌ Hidden | 🔑 View & manage own issued keys |
| **Editor** | Domain-bound (e.g., `editor@example-a.com`) | ✅ Full access | 🔍 View only logs generated by own session | 👁️ View global & own org loaded vectors | ✅ Upload documents / skills for own domain | ❌ No access | ❌ Hidden | 🔑 View & manage own issued keys |
| **Admin (Domain)** | Domain-bound (e.g., `admin-1@example-a.com`) | ✅ Full access | 🔍 View logs of all users in own domain | 👁️ View global & own org loaded vectors | ✅ Upload documents / skills for own domain | ✅ Full management for users in own domain | ❌ Hidden (Host container protection) | 🔑 View initial JWT requests in own domain |
| **Admin (Global)** | No domain (`admin`) | ✅ Full access | 🔍 View all system logs across all domains | 👁️ View all vectors across all tenants | ✅ Upload documents / skills (Global or domain) | ✅ Full management across all domains | ✅ Full access to Container Mgr | 🔑 View all initial JWT requests across all tenants |

- **User**: Can use the chat and view the telemetry page. Can only view logs that they generate. In the VectorDB Mgnt page, can view the list of global data and data loaded by their org, but cannot load documents.
- **Editor**: Can do everything the User can do, plus load documents and skills into the VectorDB page for their own domain.
- **Admin (Domain)** (e.g. `admin-1@example-a.com` with domain role): Can do everything the Editor can do and view logs of all users in their domain. Can manage user accounts for their domain in the "Password Mgnt & JWT" page and view initial JWT requests for users in their domain.
- **Admin (Global)** (`admin` with no domain): Global administrator able to manage everything across all domains and host containers. No changes to global admin capabilities.

The Main App window should have:
  - If the static/images folder have a file called tab-icon.gif, use it as the icon for the tab
  - If the static/images folder have a file called app-icon.gif, put it on the left side of the App name at the top left of the window
  - Six tabs with appropriate icon to the left of each tab name:
    1. Chat & Knowledge Mgnt
    2. VectorDB Mgnt
    3. Telemetry
    4. Log Viewer
    5. Container Mgr (Visible only to Global Admin)
    6. Password Mgnt & JWT
  - Add a button to the right of the six tabs called "Logout"
    - When the user clicks this button, close the current tab and go to the login window.
  - On the right side of the screen, put a button in the light red color “Shutdown” button
    - When the user clicks this button, open a dialog box warning the user that this will shutdown the app and all the services. All the users will be affected by this action. Confirm by typing “Shutdown the services” in the text box.
    - Show two buttons in the dialog box: Cancel, and Confirm. The confirm box should be disabled until the user typed the exact word in the text box.
    - When the user clicks “Confirm” shutdown all the services started by the app. If some of the supporting services were running before the app started, do not shut them down.
  
### 🗣️ First Page: "Chat & Knowledge Mgnt"
- Put a drop down box showing the currently selected model at the right side of the page title.
  - On start up, get the list of ONLY active LLM models for text generation from Google AI Studio API that are capable of synthesizing and outputting text then list them in the dropdown.
  - Use the GEMINI_MODEL as the default model. If the model is not available, select the first model in the list as the default model.
  - Include the option to select a Custom model. When the Custom model is selected, show a text box for the user to enter the API Endpoint of the model. The default text should be the last endpoint entered. If none exists, put “http://127.0.0.1:8010/v1/chat/completions”.
  - To the left of the model choice dropdown, add a box to allow the user to select the “Temperature” parameter to send to the model.
  - To the left of the temperature box, add a text box to allow the user to set the “Max Tokens” parameter to send to the model. Do not allow the user to set the number larger than the max tokens of the model selected.
  - Add a "Reset Defaults" button (`#btnResetChatConfig`) in the controls sub-header to reset the user's chat configuration preferences stored in `mem0` back to system defaults.
  - **mem0 User Chat Configuration Persistence**:
    - The system integrates `mem0` (via Qdrant and Gemini) to store and manage the configurable chat selections made by each user (`user_id`).
    - Stored parameters include: `model`, `temperature`, `max_tokens`, `custom_endpoint`, `agent`, `max_turns`, `rag_chunks`, `doc_threshold`, `skill_mode`, and `skill_threshold`.
    - Chat preferences are automatically restored on login / page load, updated in real time as selections change or messages are sent, and isolated between different users.
  - The following left and right cards should be the same width
    
#### Left Card: "Chat with the Agent"
- Add a drop down box called "Agent" on the right side of the card. The choices are: Custom Agent, Google ADK LlmAgent.
  - If the user selects Custom Agent, use the agent described in the Agent section of this document.
  - If the user selects Google ADK Agent, use the google ADK agent
- To the right of the "Agent" box, add a text box for the user to select the "Max Turns" the default is 5. Do not allow the user to set the number larger than 10. Use this as the maximum number of turns for the maximum Agent loop or number of turns.
- At the bottom of the card, put a text box for the user to enter the chat message.
  - Use a new conversation ID for each question
  - When the user clicks on the "Send" button or presses the Enter key, send the message to the agents container to process.
    - Use the Agents API key stored in the secrets manager
    - Include the Conversation ID of the message to the agent
    - Agent from the dropdown menu in the Chat Agent card
    - Max Turns from the text box in the Chat Agent card
    - Model Selection from the dropdown menu in the Chat page
    - Temperature from the text box in the Chat page
    - Max Tokens from the text box in the Chat page
    - Skill Selector from the dropdown menu in the Chat Agent card
    - Skill Threshold from the text box in the Chat Agent card
    - Doc Threshold from the text box in the Retrieved Context Evidence card
    - Max Chunks from the text box in the Retrieved Context Evidence card
- Use the typical chat user interface to display the chat messages and the agent's responses.
- Once the response is completed, display the response.
  - Add the detail box in the response with a button named “Show Logs”. Within the detail box, add bubbles showing the name of the components that generated the logs (such as Agent, Tools, RAG, Skills), icons appropriate for the components, and the elapse time of each step.
  - When the user clicks on the "Show Logs" button, the detail box should expand to show the full content of the step including the logs. Use the scroll area in the bubble if the content is too long.
  - Make the "Show Logs" button toggle between expand and collapse.
  - Anchor "Show Logs" button at the top-right corner of the detail box.

#### Right Card: "Retrieved Context Evidence"
- Add a box at the right side of the card named "Doc Threshold" for the user to set the threshold for the document retrieval.
  - The default value is 0.3.
  - Use this number as the minimum matching score the Document Vector Store should use to determine whether the text chunk should be returned in the query.
- To the left of "Doc Threshold", add a dropbox "Max Chunks" to allow the user to select the maximum number of RAG chunks to send to the model
  - List number of chunks: 2, 3, 5 (Default), 7, and 10
  - Use this number to limit the number of text chunks to return from the Document Vector Store query.
- In the next row, add a dropbox called "Skill Selector" to allow the user to select the skills the agent can use.
  - The first option in the dropbox should be "Vector Store Selects" (default option). The Custom Agent will query the skills vector store to select the skills to use in the prompt to the model.
  - The second option should be "LLM Selects". The Custom Agent will ask the LLM to select the skills to use in the prompt to the model.
  - The remainder of the selection should be the list of skills in skills/ folder. The Custom Agent will use the skills selected in the prompt to the model.
- Add a text box "Skill Threshold" for the user to enter the threshold when the skill selection is "Vector Store Selects".
  - Use this number as the threshold when querying the vector store.
  - The default value is 0.2.
  - Remove this box if for other selection for "Skill Selector"
- Display the contents of the information retrieved from the Document and Skill vector stores.
  - Pull the information from the Logging container related to the conversation ID for the specific chat message.
  - Group the results by the skills and documents.
  - Display the matching score from the vector store along with the name of the document.
- Allow the user to scroll through the data

### 🛢️ The second page: “VectorDB Mgnt”
- Display this page only if the user has editor or admin access
- At the same level as the page title at the right side of the page, put the statistics of the number of chunks, documents ingested, and the size of the DB in MByte. Retrieve this information from the Documents and SKills containers
- To the left of the statistic, add a button to “Update Skills Database”. When the button is selected, send the message to the Agent to load all the skills to the Documents and Skills container.

- To the left of the “Update Skills Database”, add a dropbox showing the list of Embedder that ollama can download.
  - Get the list of available models from ollama API, Display the currently running model.
  - If the user selects a different model, display a pop up window with a stern warning to the user that changing the model will delete all the data currently in the database.
    - Show two buttons: Cancel and Delete Data (initially disabled).
    - Ask the user to type the text to confirm they want to change the model.
    - When the user typed the exact text, enable the “Delete Data” button.
    - When the user clicks “Delete Data”, proceed to delete the data in the document and skill databases, then make ollama to load the new model selected.
    - After the ollama completes updating the model, scan the skills/ folder and import the skills to the skill database
    
#### Left Card: "Populate Vector Database"
- Takes a url or local directory, retrieves the documents, and sends it to the Documents & Skill containers via the Agents API to create a private vector database from documents.
  - Add a dropdown called "Type" with two options: `Documents` (default) and `Skills`. The selection allows the user to select which type of database should the document be uploaded into. The documents are loaded into the specific database collection (`documents` collection vs `skills` collection in ChromaDB).
  - Provide 5 buttons for the user to click with samples of web URL that can be imported into the database.
  - Add a sub card called “Advanced Chunking Parameters” to allow the user to select the Chunk size and Overlap in the number of characters. The sub card should be collapsed by default.
  - Add the button at the bottom to populate vector database
  - When loading the database, make sure there is no duplicated chunk
  - The card should be 40% of the page width
  - **Access Control**: Role "User" has read-only access and cannot load documents or skills; the Populate button, source input, and Reset DB button are disabled with an informational read-only notice banner. Role "Editor" and "Admin" are authorized to populate documents and skills into the VectorDB page for their own domain.

#### Right Card: “Vector Storage Status”.
- At the right side of the box put a button to allow the user to Reset the DB (enabled for Admin role).
- The card should show if the ingestion is in progress
- It should also list the name of the document ingested, the tenant domain name of the organization that stored and has access to the document (e.g., `example-a.com`, `sample-b.com`, or `All Tenants (Admin)`), the number of chunks created, and the total number of characters
- Allow the user to scroll through the list of ingested documents
- Allow the user to delete any document from the DB by using the Delete button on the right side of the document row
- The card should be 60% of the page width

#### Bottom: "Available Embedding Models".
- Display the list of available Embedding Models for the embedding service. Briefly list the characteristics including the dimensions, context window, size, brief description, and status (Installed, Active, Available to Pull).

### 📊 The third page: “Telemetry”
- The Web UI queries the Logging container's statistics and query API to compute and display the telemetry counters and timeline graphs.
- Accessible by all authenticated roles (User, Editor, Domain Admin, Global Admin).
- On the right side of the page, put the button called “Refresh Telemetry” to allow the user to manually refresh the page.
- To the left of the “Refresh Telemetry” button, add a dropdown box to list the models that have been used. Filter the contents of the telemetry page based on the model selected. Include “All Models” as the default option.
- Next, shows Total Chat (count of user chat requests), Total Prompts (model requests), Total Responses (count of LLM responses), Total Errors, Total Input Tokens, and Total Output Tokens.
- Convert and display all time stamps in the user's local time zone.

#### Top Card: "System Throughput & Token Velocity"
- Below the statistic, add a card that shows 2 graphs.
  - At the top of the box, there is a dropdown that selects the Aggregation/Refresh Interval with choices: 1 min, 15 min (default), 1 hr, and 1 day.
  - The second dropdown to the right allows the user to select the time range with options for: Last hr, 1 day (default), Week, Month and Custom. When Custom is selected, bring up two boxes with a dropdown calendar that allows the user to select the starting date and ending date. Changing the Time Range updates the charts dynamically to display the continuous time span.
  - Below the selection, the Left plot shows the line graphs of Request Throughput for "Chat Requests" (count of chat_request), "LLM Requests" (count of llm_invocation), "LLM Responses" (count of llm_response), and "Errors" per interval selected. The X-axis shows the time range selected.
  - The right plot shows the line graph of the number of input and output tokens per interval selected. The X-axis shows the time range selected.

#### Bottom Card: “Other Important Statistic not Available for Low-Performance Computer”
- Time to First Token (TTFT): The duration between a user sending a prompt and receiving the very first token. This is the most critical metric for perceived speed in streaming applications.
- Inter-Token Latency (ITL): The average time elapsed between generating each subsequent token.
- Tokens Per Second (TPS): The throughput speed of the model generation (often measured per request or aggregated across the server).
- Time Per Output Token (TPOT): The total time taken to generate the response divided by the number of output tokens.

### 📝 The fourth page: “Log Viewer” (Audit Logs & Events)
- Accessible to all authenticated roles with role-based scoping:
  - **User & Editor**: Can view only logs that they generate.
  - **Admin (Domain)**: Can view logs of all users in their domain.
  - **Admin (Global)**: Can view all system logs across all domains.
- The log records include the name of the user who sends the prompt to the Agent (`user` and `domain`).
- To the right side of the page, add a button called “Refresh” to allow the user to manually refresh the page.
- To the left of the “Refresh” button, add a button to allow the user to clear the logs (accessible to administrators). This will delete all the logs. When the user clicks on this box, open a pop up window asking the user to confirm.
- Next, display the statistics of the total user prompts logged, model calls, Ollama embeds, Avg call latency.
- Convert and display all time stamps in the user's local time zone.

#### Top table: "User Conversations (Select a row to inspect associated events)"
- Display the list of all the user conversations in the log.
  - The following columns should be displayed: Timestamp (in local time), Conversation ID, User / Sender (email/username), User Query, Agent Response, Agent Type, Number of Events (occurred during the conversation), etc.
- Only show 5 rows in the table
- There should be a scroll bar on the right side to allow the user to scroll through all the items.
- When the user clicks on a row, the next table should be populated with the logs associated with the conversation selected.
- The selected row should be highlighted.

#### Bottom table: "Events for Conversation <Conversation ID>"
Display the logs associated with the conversation selected in the table above sorted by the ascending order based on the time. The table should have columns showing:
  - Time and Date (local time)
  - Event Type
  - Invoker
  - Target
  - Short Description
  - When the row is clicked, open a pop up window to show all the detailed logs including the JSON payload in human readable format
    - The popup window should show the text in the prompt and the response in a human readable format. If the text is JSON, display it in a JSON viewer format.

### Fifth page: "Container Mgr"
- Display this page only if the user has Global Admin access (`admin` with no domain). Hidden for domain administrators, editors, and users to prevent unauthorized host orchestration.
- Display a "Shutdown All" button at the top right corner.
  - When the user clicks on this button, open a popup window asking the user to type "Shutdown System".
  - Add a text input box for the user to type "Shutdown System".
  - Add the "Confirm Shutdown" button at the bottom right of the popup.
    - This button should be disabled until the exact phrase "Shutdown System" is typed in the text input box.
    - When the user clicks on "Confirm Shutdown", shut down all the containers.
  - Add the "Cancel" button at the bottom of the popup window. When the user clicks the button, close the popup window.
- Next to the "Shutdown All" button, add a "Restart All" button.
  - When the user clicks on this button, open a popup window asking the user to type "Restart System".
  - Add a text input box for the user to type "Restart System".
  - Add the "Confirm Restart" button at the bottom right of the popup.
    - This button should be disabled until the exact phrase "Restart System" is typed in the text input box.
    - When the user clicks on "Confirm Restart", restart all the containers.
  - Add the "Cancel" button at the bottom of the popup window. When the user clicks the button, close the popup window.
- Display the containers in the system in a drawing.
  - The user should be at the top of the drawing connecting to the web ui container.
  - The containers should be displayed in a way that the user can see the relationship between the containers.
    - Draw a line to show the Web UI container connects to Agent container and Documents & Skills container to upload documents.
    - Draw a line to show the Agent container connects to the Documents & Skills container, and Tools container.
    - Draw a line to show the Documents & Skills container connects to the Embedding container.
    - Draw a dash line to show all the containers connected to the Authentication and Logging containers.
  - The container should have light green when it is active and light red when it is stopped or failed to start.
  - When the user right clicks on any container, open a popup window with the following information:
    - Container name and Status
    - Add the highlighted text "API Keys can be set when the container is inactive."
    - List of containers that the container accesses.
      - If the container is an active container, the list is read only.
      - If the container is inactive, the user can add the API key for each container in the list.
    - If the container is inactive, show a Start button in green color. If the container is active, there should be a Stop button. Show the button in red color. The button should be at the bottom right corner.
    - Add a "Close" button at the bottom left corner. Close the popup window when the user clicks the button.

The Agent container accesses:
  - Authentication service to authenticate the API key provided by the web ui
  - Documents and Skills container to request for documents or skills for a given query.
  - Tools container to access the tools for a given query.
  - Logging container to log the agent container's activity.

The Documents and Skills container accesses:
  - Authentication service to authenticate the JWT token provided by the web ui
  - Logging container to log the agent container's activity

### 🔑 Sixth page: “Password Mgnt & JWT”
- At the top right of the page header, includes a **Refresh** button (`#btnRefreshAuth`) that refreshes and updates all tables on the page (User Accounts, User Access Activity, Active Session, JWT List, and JWT Activities).
- Accessible to administrators to manage credentials, users, and tokens. Non-admin users are notified that Admin access is required.
- Admin access displays two sub-tabs: Passwords and JWT (JSON Web Token)
  - Passwords tab displays:
    - User Account Directory table:
      - Only allow users with Admin access to make any changes to User accounts (changing roles, locking/unlocking accounts, resetting passwords, creating new users, and deleting users).
      - Add a button named "Create New User" in the header of the User Accounts Directory.
        - When clicked, open a popup window asking the admin to enter the user name and password.
        - The popup provides "Cancel" and "Create" buttons.
        - When the "Cancel" button is clicked, close the popup window without creating an account.
        - When the "Create" button is clicked, create a user ONLY if both the user name and password are entered.
      - Add the "Delete Users" button next to "Create New User":
        - Only enable the "Delete Users" button if one or more of the checkboxes next to user names are checked.
        - Disable the button if no checkboxes are checked or if the logged-in user is not an Admin.
      - The table contains the following columns:
        - User Name: Includes an individual selection checkbox next to the user name, and a "Check All" checkbox at the column name header to select/deselect all rows.
        - Date/time when the account was created.
        - Role (allows the admin to select and change roles between Admin, Editor, and User).
        - Status badge (Active/Locked) with Lock/Unlock action toggle.
        - Actions column: Contains "Reset Pass" button to reset passwords. Note: The individual "Delete" button in the ACTIONS column is removed.
      - Only show 5 rows in the table viewport, with a scroll bar on the right side to allow scrolling through all user accounts.

    - The second table displays the list of all user access and requests:
      - The table should have columns showing: Local Date/time, User Email, Request Type, and Status
      - The table should be sorted by the descending order based on the time
      - Include Login, Logout, New User Registration, and Password Reset requests
      - Only show 5 rows in the table
      - There should be a scroll bar on the right side to allow the user to scroll through all the items

  - JWT (JSON Web Token) sub-tab displays:
    - Active Multi-Tenant Session & JWT Token panel:
      - Displays the logged-in user's identity, email address, assigned role (`Admin`, `Editor`, or `User`), and active tenant domain.
      - Displays the tenant's permitted resource boundaries:
        - Permitted RAG documents: Domain-scoped (e.g. `example-a.com` documents, `sample-b.com` documents, or ALL documents for Admin).
        - Permitted Tools CSV: `tools/data/employee_database.csv` (for `example-a.com`), `tools/data/customer_database.csv` (for `sample-b.com`), or both (for Admin).
      - Contains a "Refresh" button to scan and display the active session and keys.
      - Displays the full encoded JWT token with a "Copy Token" button.
      - System authentication relies strictly on JWT tokens. Container-level API keys have been removed; external calls (e.g., to Google AI Studio) use `GEMINI_API_KEY`.
    
    - "JWT List" table:
      - Displays all active JWT tokens issued across tenant users.
      - Columns:
        - Selection Checkbox: Each row has an individual selection checkbox, and the column header has a "Select All" checkbox.
        - User Name: The email/username of the user who owns the token.
        - Token Suffix: Displays the last several characters of the token (e.g. `...abqgxahreI`).
        - Generated Date/Time: Localized timestamp when the token was created.
        - Expiry Date/Time: Localized timestamp when the token expires.
        - Status: Token lifecycle status badge (`Active` or `Revoked`).
      - "Delete Selected JWT" button:
        - Located in the card header.
        - Enabled only when one or more row checkboxes are selected; otherwise disabled.
        - When clicked, displays a confirmation modal/popup asking for confirmation before deleting.
        - When confirmed by the admin, sends a bulk deletion request to remove the selected tokens from the list and database.
      - Row Selection Filtering:
        - Clicking anywhere on a row in "JWT List" highlights that row and filters the "JWT Activities:" table below strictly for that token/user.
        - Clicking the selected row again deselects it, restoring the "JWT Activities:" view to show activities for all tokens.

    - "JWT Activities:" table:
      - Header indicates whether activities are filtered for a specific token/user or "All Tokens".
      - Contains a "Refresh" button to refresh the JWT activities log.
      - Lists the usage of the JWT from the user, listing ONLY the initial request from the user.
      - Sub-calls between internal containers (e.g. internal LLM invocations, agent tool calls, embedding queries) are filtered out so that only primary user-initiated requests are displayed.
      - The table contains the following columns:
        - Local Date / Time
        - User / Sender
        - Tenant Domain
        - Endpoint / Recipient
        - Action / Request Type
        - Status
        - Initial Request Details
      - Scoped by tenant domain for Domain Admins, scoped to own requests for Users, and global view for Global Admin.
      - Linked to Log Viewer so all raw logs and initial request activities show up reliably.

## Container Requirements
- The project should be run using Docker.
- Create a docker-compose.yml file to run all the containers.
- All the files created for the container should be in the container's own folder
- Use Python as the default language for all the code in the containers
- All containers should use API keys for authentication and determine what they are allowed to do.
- Use TCP port 8000 for the Web UI container.
- Use TCP port 8001 for the Authentication Service container.
- Use TCP port 8002 for the Agent container.
- Use TCP port 8003 for the Documents and Skills Vector Store container.
- Use TCP port 11434 for the Ollama Vector Embedding container.
- Use TCP port 8005 for the Tools container.
- Use TCP port 8006 for the Logging container.
- All of the containers should send all the logs to the Logging container using the Logging service API.

### Web UI
- Create a soft link from the ./.env file to the web_ui/secrets/.env file
- Create a container for the web UI in the web_ui/ folder for all files related to this web UI
  - The secrets/ folder in the container should map to the web_ui/secrets/ folder on the host. Use volume to persist the secrets/ on the host
  - Authenticate all inter-container requests using the active user's JWT token issued at login
  - Import GEMINI_MODEL from the secrets/.env file and use it as the default model to make the request to the agent
  - Mount the host Docker socket /var/run/docker.sock to /var/run/docker.sock inside the web_ui container so that the Container Manager can monitor container health/resources and trigger Start/Stop/Restart actions using the Python docker SDK
  - Provide the access to the UI described above.
  - Create a unique Conversation ID for each chat message.
  - When sending a request to the Agent container, include the user's login JWT token in the `Authorization: Bearer <token>` header.

  - Create a log when the user:
    - Logs in and out of the system with:
      - the user name
      - IP address
      - time of login and logout
    - Views different pages in the web UI with:
      - the user name
      - IP address
      - time the page was viewed
      - name of the page being viewed

### Authentication Service
- Create a container for the authentication & authorization services in the auth_service/ folder
  - Persist user accounts in an SQLite database mounted to host ./auth_service/secrets/ volume.
  - Seed a default initial Admin account on first startup: username: admin, password: admin123
  - Manages user accounts and JWT authentication as described in the "Password Mgnt & JWT" page in the web UI.
  - When a new user account is created, it is initially set to "Locked" status. The administrator can unlock the account via the UI.
  - Generates and verifies cryptographically signed JWT tokens containing the user's email, role, and tenant domain for inter-container communication.

  - Create a log of user authentication and JWT usage, and send them to the Logging container using the Logging service API.

### Agents
- Create a container for the agent in the agents/ folder.
  - Use FastMCP server with async HTTP transport as an interface to provide access to all the services. 
  - Link the .env from the root folder to the agents/secrets folder
  - The secrets/ folder in the container should map to the agents/secrets/ folder on the host. Use volume to persist the secrets/ on the host
  - Upon start up:
    - import GEMINI_API_KEY from the secrets/.env file for external calls to Google AI Studio
    - The app should scan the agents/skills/ folder and load the skills that are not currently in the skills vector database.
  - Use GEMINI_API_KEY to make the external LLM calls using Google genai library. Authenticate inter-service calls (to Vector DB and Tools) strictly using the user's JWT token.

  - The skills folder structure should as follow:
  ```
  ├── agents/                    # Custom and Google ADK Agent microservices (Port 8002)
  │   └── skills/                # Domain skills (SKILL.md, tools, and trigger queries)
  │       ├── <skill_name>/      # Skill folder (e.g., time-weather-skill)
  │       │   ├── SKILL.md       # Skill metadata and SOP
  │       │   └── scripts/       # Python scripts for tools
  │       │       └── tool_*.py  # Tool scripts (e.g., env_tools.py)
  │       └── <another_skill>/   # Another skill folder
  │           ├── SKILL.md       # Skill metadata and SOP
  │           └── scripts/       # Python scripts for tools
  │               └── tool_*.py  # Tool scripts
  ```

  - Create two agents: Custom agent and Google genai agent.
    - All Custom agents should be in the agents/custom_agent/ folder
    - All Google genai agents should be in the agents/genai/ folder

#### The Custom Agent
The Custom Agent should operate as follow:
  - When it receives the message from the user, check the Skills selection in the request:
    - If it is "Vector Store Selects" use the skills vector store to find the skills that have a higher matching score than the minimum threshold set by the user.
    - If it is "Use AI Agent with Tools" send the name and description of all skills to the LLM and use the simple system prompt asking the LLM to determine if it should use any of the skills to answer the question.
    - If it is "Skill: xxxxxx", then send the user message and the skill description to the LLM to get the instruction or plan for the tool execution.
  - If no skill is found, send the user query to the LLM using the simple system prompt as an assistant to answer the question.
  - If there are multiple skills found, send the user message and the 2 highest matching skills to the LLM to get the instruction or plan for the tool execution.
  - The system prompt should ask the LLM to determine if any of the tools should be invoked to gather more information to answer the question.
  - The system prompt should ask the LLM to respond with JSON format indicating the tool to be executed and the arguments to be passed to the tool. For example:
  ```
    {
      "tool": "person_search.query_person_registry",
      "arguments": {
        "keyword": "Lucas Dubois",
        "field": "name"
      }
    }
  ```
  - If the LLM determines that a procedural tool should be executed, execute the tool to obtain the needed information. Send a prompt to the LLM with the results from the tool. Repeat until the final answer is received. Limit the number of loops no more than MAX_LLM_TURNS.
  - Minimize skill-specific code in the orchestrator
  - The last llm call should use a typical system prompt as an assistant to answer the question. The final output of the agent is the response from this last LLM call.
  - Only perform vector search for documents when the skill search result and the model direct the Agent to perform the search.
  - Minimize the number of loops to obtain the final answer. The maximum number of loops should be Max turns configured in the GUI.
  - Format the final output to make it easy for human reading and understanding.

#### Google ADK Agent
- Create a python code in agents/genai/ folder to use LlmAgent from Google ADK.
- Use the model selected in the Chat & Knowledge Synthesis page.
- Set the agent_type to "Google ADK Agent" and add it to the log record.
- Use the skills and tools available in the skills/ folder.
- Create logs for all the invocations and responses when the Agent is invoked.
  - Include all the details needed to show in the Audit Log & Event page.
  - Create logs when the Agent invokes and receives response from the model. Include the actual payload.

#### Logs
- Create logs for all the calls / invocations and responses between the following components. The log should include the actual details of the payloads passed to and from the components. 
  - agent - log the complete messages including actual payload:
    - Sent to the agent
    - sent/calls from the agent to: tools, ollama, vector store, MCP, and LLM.
    - All the responses received from the calls and the LLM
  - LLM - prompts sent to and response received from the model include the FULL payload. Log the model invocation and response. Include the FULL PAYLOAD.
  - In all of the logs, include the time of the call, the type of the call, the invoker, the recipient, and all the raw payload passed in the message.

#### Sample Skills and Tools
- Create the following skills using the agents/skills folder structure. The skills should at least have the name, description, Trigger Queries, etc:
  - Write the SKILL.md file to get the time and weather of the city in the query.
    - Create the python code in the agents/skills/<skill_name>/scripts/ folder that will get the time and weather of the city in the query. Use a site that doesn't require API key to get the data
  - Write the SKILL.md file to get the list of stocks with the highest percentage increase or lowest percentage decrease based on the chat question.
    - Create the python code in the agents/skills/<skill_name>/scripts/ folder that will get the list of stocks with the highest percentage increase or lowest percentage decrease based on the chat question. Call the tools container to get the response.
  - Write the SKILL.md file to get the list of top k text chunks from the document vector database.
    - Call the tools container to get the response.
  - Write the SKILL.md file to get the name, city, country, or job title of the person in the CSV file.
    - Call the tools container to get the response.

### Documents and Skills
- Create a doc_RAG container in the doc_RAG/ folder.
  - Use FastMCP server with async HTTP transport as an interface to provide access to query the documents and skills vector store databases.
  - The secrets/ folder in the container should map to the doc_RAG/secrets/ folder on the host. Use volume to persist the secrets/ on the host
  - Authenticate incoming requests using the JWT token sent in the request Authorization header or body
  - Use chromadb to store the documents and skills vector database
  - Each record should contain:
    - type: "document" or "skill"
    - name: name of the document or skill
    - date_time: date and time of upload
    - vector_text: the text chunk or complete text of the skill
    - vector: the vector of the text chunk or complete text of the skill

  - The vector store database has the following services:
    - List all the documents and skills:
      - The request must contain:
        - N/A
      - Response should include:
        - the list of documents and skills imported in the vector store group by type(documents, skills)
        - Number of documents and skills
        - The size of the database

    - Add New Document:
      - Allow users with edit or admin permission to add new documents.
      - The request contains:
        - User ID. Required
        - Document type (document, skill). Required
        - Document name. Required
        - Complete text of the document or skill. Required
        - Chunk size. Required for document type "document"
        - Overlap. Required for document type "document"
      - Response should indicate success or failure

      - If document type is "skill":
        - Use the "vector_text" to create the vector for this skill
        - Store the skill name, vector, date & time of upload, and the complete text of the skill in the vector database

      - If document type is "document":
        - Split the complete text of the document into chunks using the Chunk size and Overlap parameter sent in the request
        - Generate vectors for each chunk via the embedding container
        - Store each chunk record (document name, date & time of upload,  chunk text, chunk index, vector) in the vector database

    - Delete a document:
      - Allow users with edit or admin permission to add new documents.
      - The request must contain:
        - User ID. Required
        - Document type (document, skill). Required
        - Document name or ALL. Required
      - Response should indicate success or failure

    - Query Documents:
      - The request contains:
        - User ID. Required
        - Conversation ID. Required
        - Document type (document, skill). Required
        - K (number of results). Optional. Default is 5
        - Threshold (similarity score). Optional. Default is 0.3
        - Query String. Required
      - Response should include:
        - The list of documents and skills that matched the query
        - The similarity score of each document and skill
        - The chunk text of each document and skill

  - Create logs of all the communication between the request container and the vector store container:
    - All records should include the name of the service "Vector DB" or "Embedding" (depending on which service is being called), user id, conversation id (if applicable), date and time, and type of operation.
    - For Add: Include the document type, document name, chunk size and overlap (if applicable), and success status.
    - For Delete: Include the document type, document name, and success status.
    - For Query to Vector DB:
      - One record for the request: include the document type, k, threshold, and query string.
      - One record for the response: include the list of document chunks or skills that matched the query, and the similarity score of each document chunk or skill

    - For Query to the Embedding Service:
      - Include the model used to embed the documents and skills

### Embedding
- Create an embedding container in the embedding/ folder.
  - Use the embedding container from ollama
  - Provide the API access to query the embedding service for:
    - The model that is currently loaded to embed the documents and skills
    - The list of available embed models in ollama
  - If the user has edit or admin permission, allows the following:
    - Change or update the model used to embed the documents and skills

### Tools
- Create a tools container in the tools/ folder.
  - Use FastMCP with async HTTP transport to serve all the access to the tools in the container. 
  - Inter-service requests use the JWT token from the user's login as the main authentication:
    - The domain claims inside the JWT token enforce which CSV database can be accessed:
      - `example-a.com` is authorized to access `tools/data/employee_database.csv`.
      - `sample-b.com` is authorized to access `tools/data/customer_database.csv`.
      - Admin login with no domain (or role `Admin`) is authorized to access BOTH CSV files.
    - If a tenant attempts to access an unauthorized CSV file or invoke an unauthorized tool, the service returns HTTP 403 Forbidden.
  - All container-level API keys have been removed; inter-container communication uses the login JWT token exclusively.
  - All the calls must include Conversation ID to allow the logging service to track the calls.
  - The container should have a volume data/ mounted to ./tools/data/ on the host hard drive to persist any data.

  - Create logs of all the calls to the tools service. Include: 
    - Conversation ID
    - invoker
    - tool name
    - date and time of the call
    - arguments
    - complete request and response payload.

  - Create seeding scripts to populate the tools service with data:
    - The first tool script "employee_search" (`person_search.query_person_registry`) provides information about employees from `tools/data/employee_database.csv` (accessible to `example-a.com` and Admin).
      - Populated with 30 employee records with name, city, country, and job title.
    - The second tool script "customer_search" (`customer_search.query_customer_registry`) provides customer records from `tools/data/customer_database.csv` (accessible to `sample-b.com` and Admin).
      - Populated with 20 random customer records containing name, address (with city and country info), and a list of 3 to 5 products purchased.
    - The third tool script "stock_analysis" gets the list of stocks with the highest percentage increase or lowest percentage decrease based on criteria from the arguments in the function call.
    - The fourth tool script "time_weather" queries live time and weather for any city worldwide.

### Logging & Telemetry System
- Create a central logging service container in the `logging/` directory to capture, persist, and aggregate logs from all entities across the microservice mesh.
  - Logs are persisted in `logging/logs/log.json` on the host via volume mount `./logging/logs:/app/logs`.
  - Maintain operational statistics including total log count, entity distribution, file size, token throughput, and latency.

#### Inter-Container Full Payload Logging Requirements
All container-to-container communications must record the complete, untruncated payload in the log entries. The following events must be logged with their exact request and response objects:
1. **Web UI ➔ Agents Service**:
   - `chat_request`: User prompt, model selection, temperature, max_turns, and agent settings.
   - `chat_response`: Synthesized final answer, full execution steps list, duration in milliseconds (`duration_ms`), and model.
2. **Agents Service ➔ Vector Store (`doc_rag`)**:
   - `skill_vector_query` / `vector_db_query_request`: Query string, threshold, limit (`k`), document type (`skill` or `document`).
   - `skill_vector_response` / `vector_db_query_response`: Matched skills or document chunks including complete chunk text, similarity score, and metadata.
3. **Vector Store (`doc_rag`) ➔ Embedding Service (`ollama`)**:
   - `embedding_query`: Full text to embed, embedding model name (`model_used`), vector dimension, and embedding duration (`duration_ms`).
4. **Agents Service ➔ LLM Model**:
   - `llm_invocation`: Full prompt text, system instructions, temperature, max tokens, and model identifier.
   - `llm_response`: Full generated text response, prompt token count (`input_tokens`), completion token count (`output_tokens`), duration (`duration_ms`), and model.
5. **Agents Service ➔ Tools Service**:
   - `tool_invocation`: Target tool name, function arguments.
   - `tool_response`: Structured tool output, execution status, and duration (`duration_ms`).

#### Standard Log Entry Schema
```json
{
  "id": "log_1790638137273_061f",
  "timestamp": "2026-09-28T23:28:57.270953+00:00",
  "type": "chat_response",
  "invoker": "agents",
  "recipient": "Web UI",
  "conversation_id": "conv_1790638137",
  "short_description": "Web UI received response from agent (8408ms)",
  "payload": {
    "request": { ... },
    "response": { ... }
  },
  "status": "success",
  "duration_ms": 8408,
  "input_tokens": 863,
  "output_tokens": 7,
  "model": "gemini-3.1-flash-lite",
  "is_error": false
}
```

#### Automatic Metadata Extraction & API Key Redaction
- **Automatic Metadata Extraction**: If root-level `duration_ms`, `model`, `input_tokens`, or `output_tokens` are omitted by the caller or set to `0`/`""`, the logging service automatically extracts them from `payload.response.duration_ms`, `payload.request.model_used`, `payload.token_usage`, etc.
- **Recursive Redaction**: All API keys (e.g. `AIza...`, `sk-...`, `key-...`, or dictionary keys matching `api_key`, `secret`, `password`) are automatically masked as `****` prior to disk persistence.

## 🔌 Microservices API Reference

### 1. Web UI Service (`web_ui`, Port 8000)
- `GET /`
  - Serves the unified multi-tab Web Application dashboard.
- `POST /api/auth/login`
  - Validates user credentials with Auth Service and initializes user session.
  - Request: `{"username": "<user>", "password": "<pass>"}`
  - Response: `{"status": "success", "user": {"email": "<user>", "role": "Admin|Editor|User", "status": "Active"}}`
- `POST /api/auth/logout`
  - Logs user logout event, terminates session, and returns to login popup.
- `POST /api/auth/register`
  - Registers a new user account with initial "Locked" status.
  - Request: `{"username": "<user>", "password": "<pass>"}`
- `POST /api/page_view`
  - Records user page navigation event for auditing.
  - Request: `{"page_name": "<page>", "username": "<user>", "session_id": "<id>"}`
- `GET /api/models`
  - Proxies to Agents service to return active text generation models.
- `POST /api/chat`
  - Proxies user chat prompt and configuration parameters to Agents container.
  - Request: `{"message": "<text>", "agent_type": "...", "model": "...", "max_turns": 3, "temperature": 0.7, ...}`
- `GET /api/vectordb/stats` & `GET /api/rag/stats`
  - Proxies vector store statistics (total chunks, total documents, database size in MB, active embedding model) from doc_RAG.
- `GET /api/vectordb/documents` & `GET /api/rag/documents`
  - Proxies document list from doc_RAG with per-document metadata: document name, chunk count, and total character count.
- `GET /api/vectordb/models` & `GET /api/vectordb/ollama_models`
  - Returns embedding models catalog (name, dimensions, context window, size, description, status, is_active, is_installed) based on Ollama tags and active embedder.
- `POST /api/vectordb/ingest` & `POST /api/vectordb/populate`
  - Ingests content from a URL or local file/directory path into doc_RAG with configurable chunk size and overlap parameters.
- `DELETE /api/vectordb/document` & `DELETE /api/vectordb/delete/<name>` & `DELETE /api/rag/documents/<name>`
  - Deletes all chunks associated with a specific document or all documents from the vector database.
- `POST /api/vectordb/change-model` & `POST /api/vectordb/change_model`
  - Changes the active embedding model, resets document vector database, and triggers skill re-indexing.
- `POST /api/keys/bulk_delete`
  - Proxies bulk API key deletion to the Auth Service.
- `GET /api/telemetry`
  - Proxies operational telemetry, token throughput, velocity timeline charts, and inference performance metrics from Logging service.
  - Query parameters: `model` ("All Models" or specific model), `interval` ("1 min", "15 min", "1 hr", "1 day"), `time_range` ("Last hr", "1 day", "Week", "Month", "Custom"), `start_date`, `end_date`.
- `GET /api/logs` & `GET /api/audit/conversations`
  - Proxies conversation audit list and aggregate statistics pill metrics (`total_user_prompts`, `total_model_calls`, `total_ollama_embeds`, `avg_latency_ms`).
- `GET /api/logs/<conv_id>` & `GET /api/audit/events/<conv_id>`
  - Proxies chronological event traces and complete request/response payloads for a conversation ID.
- `POST /api/logs/clear` & `POST /api/audit/clear`
  - Clears all recorded logs from the logging database.
- `GET /api/containers/status` (or `/api/containers/list`)
  - Queries local Docker socket (`/var/run/docker.sock`) to report status, CPU%, and memory usage of all 7 containers.
- `POST /api/containers/<name>/action`
  - Executes container action (`start`, `stop`, `restart`) via Docker SDK.
- `GET /api/jwt/activities`
  - Returns only the initial requests from the user (chat queries, vector ingest/deletion, login/logout, page views) extracted from the centralized logging service, filtered by user/tenant scoping.
- `POST /api/system/shutdown` & `POST /api/system/restart`
  - Executes system-wide graceful shutdown or restart.

### 2. Authentication & Authorization Service (`auth_service`, Port 8001)
- `GET /health`
  - Health check endpoint returning service status and port.
- `POST /api/auth/login`
  - Authenticates username and password against SQLite database (`auth.db`).
  - Generates and returns a signed multi-tenant JWT token containing user email, role, and domain.
  - Request: `{"username": "<str>", "password": "<str>", "ip_address": "<str>"}`
  - Response: `{"status": "success", "jwt_token": "<jwt>", "user": {"id": 1, "email": "...", "role": "...", "status": "Active"}}` (or 401 Unauthorized / 403 Forbidden for Locked status).
- `POST /api/auth/logout`
  - Logs user logout activity and writes to activity log.
  - Request: `{"username": "<str>", "ip_address": "<str>"}`
- `POST /api/auth/register`
  - Registers a new account with default status `Locked`.
  - Request: `{"username": "<str>", "password": "<str>", "ip_address": "<str>"}`
  - Response (201): `{"status": "success", "message": "Account created in Locked status", "user_id": <int>}`
- `GET /api/users`
  - Lists all registered users with roles, statuses, and creation timestamps.
- `PUT /api/users/<id>/status`
  - Updates account status (`Active` or `Locked`). Admin only.
  - Request: `{"status": "Active"|"Locked"}`
- `PUT /api/users/<id>/role`
  - Updates user role (`Admin`, `Editor`, `User`). Admin only.
  - Request: `{"role": "Admin"|"Editor"|"User"}`
- `POST /api/users/<id>/reset_password`
  - Resets password for the specified user account.
  - Request: `{"password": "<new_password>"}`
- `DELETE /api/users/<id>`
  - Deletes user account from the system. Admin only.
- `GET /api/users/activity_logs`
  - Returns chronological table of user access and authentication events.

### 3. Agents Service (`agents`, Port 8002)
- `GET /health`
  - Health check endpoint returning service status and port.
- `GET /api/agents/models` (or `GET /api/models`)
  - Fetches active text generation models from Google AI Studio / Gemini API and returns model metadata (ID, display name, max input/output tokens, and default model).
  - Response: `{"models": [...], "default": "gemma-4-26b-a4b-it"}`
- `GET /api/agents/skills`
  - Returns list of domain skills discovered and loaded from the `skills/` directory.
- `POST /api/agent/chat`
  - Orchestrates autonomous multi-turn reasoning and tool invocation for user queries.
  - Request:
    ```json
    {
      "message": "<user query>",
      "conversation_id": "conv_<timestamp>",
      "agent_type": "Custom Agent" | "Google ADK Agent",
      "model": "<model_id>",
      "temperature": 0.7,
      "max_tokens": 2048,
      "max_turns": 3,
      "skill_selector": "Vector Store Selects" | "LLM Selects" | "<skill_name>",
      "skill_threshold": 0.2,
      "doc_threshold": 0.3,
      "max_chunks": 5,
      "api_key": "<agent_api_key>"
    }
    ```
  - Response:
    ```json
    {
      "status": "success",
      "response": "<formatted answer>",
      "conversation_id": "...",
      "agent_type": "...",
      "model": "...",
      "duration_ms": 1420,
      "steps": [...],
      "logs": [...]
    }
    ```
- `GET /sse`
  - FastMCP SSE endpoint for async client connections.
- `POST /messages`
  - FastMCP protocol message dispatcher.

### 4. Documents & Skills Vector Store Service (`doc_RAG`, Port 8003)
- `GET /health`
  - Health check endpoint returning service status and port.
- `GET /api/rag/list` (or `GET /api/rag/documents`, `GET /api/rag/stats`)
  - Lists all ingested documents and skills grouped by type, total counts, and storage size.
  - Response: `{"status": "success", "documents": ["doc1", ...], "skills": ["skill1", ...], "count_documents": 1, "count_skills": 4, "chunks_count": 5, "db_size_mb": 0.74}`
- `POST /api/rag/add` (or `POST /api/rag/documents/add`)
  - Adds a new document or skill to the ChromaDB vector database.
  - Request:
    ```json
    {
      "user_id": "<user_id>",
      "type": "document" | "skill",
      "name": "<name>",
      "text": "<complete text>",
      "chunk_size": 800,
      "overlap": 100,
      "vector_text": "<text to embed>",
      "api_key": "<api_key>"
    }
    ```
  - Response: `{"status": "success", "type": "...", "name": "...", "chunks_created": <int>}`
- `POST /api/rag/delete` (or `POST /api/rag/documents/delete`, `DELETE /api/rag/documents/<name>`)
  - Deletes document or skill by name, or wipes entire collection if name is `"ALL"`.
  - Request: `{"user_id": "<user_id>", "type": "document"|"skill", "name": "<name>|ALL"}`
  - Response: `{"status": "success", "deleted_records": <int>}`
- `POST /api/rag/query`
  - Performs semantic vector similarity search against document chunks or skills. Emits separate request and response audit logs to Logging container.
  - Request:
    ```json
    {
      "user_id": "<user_id>",
      "conversation_id": "conv_<id>",
      "type": "document" | "skill",
      "query": "<search text>",
      "k": 5,
      "threshold": 0.3,
      "api_key": "<api_key>"
    }
    ```
  - Response:
    ```json
    {
      "status": "success",
      "type": "document",
      "count": 1,
      "results": [
        {
          "name": "<doc_name>",
          "similarity_score": 0.72,
          "chunk_text": "<text>",
          "metadata": {"type": "document", "name": "...", "date_time": "...", "chunk_index": 0}
        }
      ]
    }
    ```
- `POST /api/rag/reset`
  - Clears all document vectors from ChromaDB. Admin only.
- `GET /sse` & `POST /messages`
  - FastMCP async interface exposing `query_documents` and `query_vector_db` tools.

### 5. Procedural Tools Service (`tools`, Port 8005)
- `GET /health`
  - Health check endpoint returning service status and port.
- `GET /api/tools/list`
  - Returns directory of available tools, schemas, and argument specifications.
- `POST /api/tools/call`
  - Dispatches and executes tool logic. Validates API key and emits invocation/response logs.
  - Request:
    ```json
    {
      "tool": "person_search.query_person_registry" | "stock_search.query_stocks",
      "arguments": {"keyword": "Dubois", "field": "name"},
      "conversation_id": "conv_<id>",
      "api_key": "<api_key>"
    }
    ```
  - Response: `{"tool": "...", "result": {...}, "status": "success", "duration_ms": 12}`
- `GET /sse` & `POST /messages`
  - FastMCP async interface exposing `person_search.query_person_registry` and `stock_search.query_stocks`.

### 6. Central Logging & Telemetry Service (`logging`, Port 8006)
- `GET /health`
  - Health check endpoint returning service status, service name, and port 8006.
- `POST /api/logs`
  - Ingests structured audit log events with automatic metadata fallback and API key redaction.
  - Request body:
    ```json
    {
      "invoker": "<source>",
      "recipient": "<target>",
      "conversation_id": "<conv_id>",
      "type": "chat_request|chat_response|llm_invocation|llm_response|embedding_query|...",
      "short_description": "<summary>",
      "payload": {
        "request": { ... },
        "response": { ... }
      },
      "status": "success|error",
      "duration_ms": 120,
      "input_tokens": 512,
      "output_tokens": 128,
      "model": "..."
    }
    ```
  - Response (201): `{"status": "success", "log_id": "log_..."}`
- `GET /api/conversations` & `GET /api/logs`
  - Returns conversations list with aggregate summary pill statistics:
    ```json
    {
      "conversations": [
        {
          "conversation_id": "conv_1790638137",
          "timestamp": "2026-09-28T23:28:57.270953+00:00",
          "first_seen": "2026-09-28T23:28:45.120300+00:00",
          "last_seen": "2026-09-28T23:28:57.270953+00:00",
          "user_query": "What is the capital of France?",
          "agent_response": "The capital of France is Paris.",
          "agent_type": "Custom Agent",
          "event_count": 11,
          "events_count": 11,
          "model": "gemini-3.1-flash-lite"
        }
      ],
      "statistics": {
        "total_user_prompts": 18,
        "total_model_calls": 20,
        "total_ollama_embeds": 108,
        "avg_latency_ms": 1572.4
      }
    }
    ```
- `GET /api/conversations/<conversation_id>/events` & `GET /api/logs/<conversation_id>`
  - Returns the chronological sequence of all communication events recorded for a conversation, enriched with `local_time`, `event_type`, `target`, `elapsed_ms`, and raw `payload`.
- `GET /api/logs/telemetry`
  - Computes operational telemetry and token velocity timeline metrics.
  - Query parameters:
    - `model`: Model filter string ("All Models" or specific model name).
    - `interval` / `raw_interval`: Bucket size ("1 min" / "1m", "15 min" / "15m", "1 hr" / "1h", "1 day" / "1d").
    - `range` / `time_range`: Time window ("Last hr" / "1h", "1 day" / "1d", "Week" / "7d", "Month" / "30d", "Custom").
    - `start_date`, `end_date`: ISO timestamps for custom range.
  - Response:
    ```json
    {
      "used_models": ["bge-large:latest", "gemini-3.1-flash-lite", ...],
      "models_used": ["bge-large:latest", "gemini-3.1-flash-lite", ...],
      "summary": {
        "total_chat": 24,
        "total_prompts": 82,
        "total_responses": 77,
        "total_errors": 18,
        "total_input_tokens": 200935,
        "total_output_tokens": 5005
      },
      "performance": {
        "avg_latency_ms": 2510.4,
        "ttft_ms": 878.6,
        "itl_ms": 930.7,
        "tps": 0.86,
        "tpot_ms": 1163.38
      },
      "charts": {
        "labels": ["04:30", "04:45", ...],
        "chat_requests": [0, 1, ...],
        "llm_requests": [0, 2, ...],
        "llm_responses": [0, 2, ...],
        "errors": [0, 0, ...],
        "input_tokens": [0, 863, ...],
        "output_tokens": [0, 7, ...]
      },
      "timeline": [...]
    }
    ```
- `GET /api/logs/query` (or `POST /api/logs/query`)
  - Filter logs by criteria: `entity`, `conversation_id`, `type`, `model`, `start_date`, `end_date`, `limit`.
- `GET /api/logs/stats`
  - Returns total log counts, file size in bytes and megabytes, and log count breakdown per entity.
- `POST /api/logs/clear`
  - Wipes all logs from `logging/logs/log.json` and resets statistics.

### 7. Ollama Embedding Service (`ollama`, Port 11434)
- `POST /api/embeddings`
  - Generates high-dimensional vector embeddings for input text.
  - Request: `{"model": "bge-large:latest", "prompt": "<text>"}`
  - Response: `{"embedding": [0.012, -0.045, ...]}`
- `GET /api/tags`
  - Lists downloaded and available embedding models.
- `POST /api/pull`
  - Downloads / pulls a specified embedding model.

## Sample Documents
- Create the sample knowledge documents in the `sample_docs/` folder:
  1. `agent_and_rag.md`: Overview of autonomous agents and RAG technology (~3000 words). Tagged to domain `example-a.com`.
  2. `company_marketing_strategy.md`: Enterprise marketing strategy and expansion framework (~3000 words). Tagged to domain `example-a.com`.
  3. `financial_report.md`: Corporate annual financial report and audited balance sheets (~3000 words). Tagged to domain `sample-b.com`.
  4. `nexus_enterprise_solutions_company_profile.pdf`: Extended corporate profile of **Nexus Enterprise Technologies Inc.** in PDF format, containing **4,000 words or more** (audited ~4,600 words). Covers executive summary, 2012-2026 corporate history, board governance, autonomous agent RAG architecture, multi-tenant domain isolation, product suites, unit economics, audited financials (FY2021-FY2025), zero-trust security & SOC 2 / ISO compliance, ESG initiatives, global office directory, and technical lexicon. Domain-tagged to `example-a.com` (and Admin).
  5. `vanguard_global_logistics_company_profile.pdf`: Extended corporate profile of **Vanguard Global Logistics & Supply Corporation** in PDF format, containing **4,000 words or more** (audited ~4,300 words). Covers corporate charter, multimodal freight infrastructure (ocean, air, rail, highway), autonomous warehouse robotics, predictive Horizon supply chain AI engine, cold-chain biopharma & dangerous goods handling, audited financials (FY2021-FY2025), fleet decarbonization (SBTi net-zero 2040), crisis contingency logistics, global port coordinates, and technical logistics standards. Domain-tagged to `sample-b.com` (and Admin).
  6. `product_catalog_100_offerings.pdf`: Commercial catalog in PDF format containing exactly **100 enterprise product offerings** (Item IDs `PRD-001` through `PRD-100`) across cloud AI compute, switches, optical transceivers, NVMe storage, firewalls/HSMs, software licenses, IoT sensors, cooling/power, and autonomous warehouse robotics. Includes Item ID, Product Name, Description, and Tiered Volume Pricing:
     - **Quantity 1**: Base Unit Price.
     - **Quantity 10 or more**: 10% price drop (`Base Price * 0.90`).
     - **Quantity 100 or more**: 30% price drop (`Base Price * 0.70`).
- Provide an automated build script (`scripts/build_all_sample_pdfs.py`) using ReportLab to regenerate all PDF documents deterministically to guarantee environment replicability.

## Misc
- Create a README.md with a brief description about:
  - what this system does
  - how to install the components needed
  - how to start all the services
  - how to shutdown all the services
  - user guide with information on how to use the system

- Create a requirements.txt and put all the libraries used by the app
