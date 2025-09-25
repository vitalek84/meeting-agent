# Meeting Agent
![Logo](./frontend/public/the-developer-logo-2-small.png)

Google Meet live AI-Agent. This is an Live AI-Agent that is able to connect or create google meet calls, manage them and play different roles in a call. 

# Demo
watch with sound

https://github.com/user-attachments/assets/3e4354c7-05d4-4551-9b28-b15c7cec4566



# Demo


# Live example
Live example is available here:
[https://thebot.thdevelop.com/](https://thebot.thdevelop.com/)

# Features 
* An agent with voice interface in a google meeting call. 
* MCP supports. Functionality of an agent may be easily extended by any MCP compatible tools. 
* Live video analysis. It receives video flow from a meeting and is able to analyse it, read google meet chat, recognize participants, etc. 
* Simple management interface - GPT like chat.  
* Scalable - it can use many google accounts and works in many meetings simultaneously. 

# Installation and Launch
## Prerequisites 
* Because you can’t connect to a google meet call w/o google account at least one google account w/o 2FA/SMS authorization required. 
* connection-manager container should be able to manage docker. So the proper path to the docker.sock should be configured. There is proper configuration in the docker-compose.yaml but if you have docker.sock in another location please configure it in the volumes section of connection-manager properly.
* It supports only the docker environment so docker should be installed. 
* If you want to connect some MCP servers they should be configured in mcp_config.json or this file should be created with dummy json.
* This project supports only Google's Gemini live agents for now so Google Aistudio account and key is necessary. [Create Google AI Studio Key](https://aistudio.google.com/apikey)
* The system assumes that you use traefik as a reverse proxy for production so it should be installed and connected to the docker network meeting-bot_default

## Configuration (Production)
**For a first launch and to get acquainted with the system - production environment is recommended**. It also may be launched w/o traefik on the localhost

* Create .env from .env_example
* Create frontend/.env.local
* Create mcp_config.json from mcp_config_example.json or put in mcp_config.json dummy json.
* These environment variables should be configured in the .env:
  * **MANAGER_GEMINI_API_KEY** - YOUR KEY - Aistudio key. Instruction how to create it may be found here: [AI Studio](https://aistudio.google.com/apikey)
  * **MANAGER_GOOGLE_ACCOUNTS** - '[{"email":"your google account", "password": "your account password"}]' - these accounts are used when the management service creates a container for google meet. At least one should be specified.
  * **MANAGER_HOSTNAME** - hostname for management service default ```localhost```. 
* This should be configured in the frontend/.env.local
  * **VITE_WEBSOCKET_HOST** - should container full url for websocket connection. Default ```ws://localhost:8000/ws```
### Start

```docker compose --profile production up```

### Notes 
* In the production environment google-meet-worker container - is a place holder that is important for container building. But real containers are managed by the connection manager. 
* For a first launch and to get acquainted with the system - production environment is recommended. 
* In the firs launch Agent logins to Google, Allows microphone and etc. So first google meet call creation/connection launch may take up to 5 minutes.

## Configuration (Development)
It makes sense to launch frontend and google meet worker in the development mode 

### Google meet workers. 
For launching google meet worker in the development mode these variables should be configured: 

* **MEET_USER_ID**=94243fe4-17dc-4025-b397-d0efd0c0e174  - is a place holder for dev mode.
* **GEMINI_API_KEY** - Aistudio key. [GOOGLE AI STUDIO](https://aistudio.google.com/apikey)
* **MEET_GM_LINK** - some_google_meet_link. Should be provided for connection to an already existing call. If it isn't provided, create a new google meet will be created. 
* **MEET_GOOGLE_EMAIL** - google account email
* **MEET_GOOGLE_PASSWORD** - google account  password
* **MEET_BROWSER_PROFILE_PATH** - /app/src/browser_profiles/my_test_profile In the production mode all browser profiles store in the volume browser_profiles in the development mode assumes that they store in a host machine in the project directory
* **MEET_AGENT_ROLE** - heart_of_gold_computer # maybe one of : software_development_manager, psychologist, heart_of_gold_computer, business_coach
* **MEET_TECHNICAL_SCREENSHOTS** - /app/src/technical_screenshots if LOG_LEVEL = DEBUG. The system saves screenshots with page control elements detected by model.
* **MEET_MANAGER_HOST_NAME** - should be ```connection-manager```

### Start

```docker compose --profile development up```


### VNC for Development mod

You can connect via localhost:5900



## A fist launch 
In the first launch an agent tries to login to google so it takes up to 5 minutes for new meeting creation.

# Debug 
Google meet worker has x11vnc and the system use standard Chrome browser so you can connect via VNC protocol and analyse how the system works. In the development mode there is port binding so you can connect to localhost:5900. In the production mode you should connect by ip directly. So you should find ip of your container in the meeting-bot_default network at fist

## MCP configuration 
The system test with Jira and Slack mcp servers for now. It should work with others but issues may be possible because MCP is still developing and some incompatibility may be.

# Architecture 
Short description of the technology stack and key points. 

## Technologies
* This agent is based on th Google live agents so it is bound to Google and it is impossible to launch it with other LLMs (for now)
* Pipewire uses for virtual audio device creation
* Selenium for Chrome management
* Pyautogui for call management. 

## Key points
The system consists from next key elements:
1. Frontend that is GPT like chat interface create as SPA on React and Vite via Bold.diy (I didn’t write a single line of code here) 
2. FastAPI (connection manager) - manages user connections and creates containers with AI agents and calls. 
3. Google meet container - contains an environment for a live agent. It connects via virtual audio devices Google Chrome and an agent logic
4. Live Agent - an agent that is based on Google live agents and can act different roles in a call. 
5. Call management logic - is an end state machine that manages call connection and inside call behaviour. 

## Call management logic
Management of Google meet calls happens via a mix of AI agent, Selenium driver, pyautogui.  So we use Selenium for Chrome launching but we detect interface elements not via css selectors or some DOM properties but by feeding screenshots to a LLM and asking for finding interface controls. When we make a decision what should we click according to the current state of our state machine.
1. Google login implemented on Selenium. 
2. All interface elements in the call and during call creation logic are detected via LLM
3. During call creation/connection we click on control elements via pyatugoi
4. For call states we use the end state machine. 

# Known Issues and Limitations

* The first launch is very slow up to 5 minutes.
* Sometimes even when an agent finishes correctly the system corrupts Chrome profile files. If it happens Chrome profile is deleted on the start up process of google meet worker and recreates again. So it again may take up to 5 minutes. In my tests it happens near 1 time in 20 launches. 
* Sometimes an agent can’t finish a call. So all participants should leave a call and then in 2 minutes the agent will quit from this call because it is able to understand that it is alone in a call .


# Add custom prompts

* Under development


# Road map 

* Move prompts to the config
* Add memory - weaviate as a vector database for Agent memory storage.
* Test with a wide range of MCP servers. 
