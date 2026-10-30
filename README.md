# UDM Firewall Toggler

## Overview

The UDM Firewall Toggler is a web application designed to manage and toggle firewall rules on a Ubiquiti Dream Machine (UDM). It requires local login credentials and direct access to the UDM. For security and accessibility, it is intended to be deployed behind an Nginx reverse proxy, allowing it to be safely exposed to the internet.

Specifically, I use it to block my kids access to the internet by blocking their devices. I create a homescreen bookmark on my wife's phone and she can block/unblock with the push of a button.

![alt text](static/image.png)

## Prerequisites

- Python 3.x
- Pipenv
- Docker
- Docker Compose

## Base Instructions

- Get your python environment setup
- `cp .env-example .env` and update it accordingly
  - Note: This will also get picked up by `docker-compose.yml`
- `pip intall -U pipenv`
- `pipenv sync`
- `pipenv shell`

## Dev/Test Instructions
- `pipenv shell`
- `./manage.py runserver 0.0.0.0:8000`

## Docker Deployment Instructions
- `docker compose up -d --build`

## Setup

1. **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd <repository-folder>
    ```

2. **Install dependencies**:
    ```bash
    pipenv install --dev
    ```

3. **Activate the virtual environment**:
    ```bash
    pipenv shell
    ```

4. **Run migrations**:
    ```bash
    python manage.py migrate
    ```

5. **Run the development server**:
    ```bash
    python manage.py runserver
    ```

## Deployment

1. **Build and deploy with Docker Compose**:
    ```bash
    docker compose up -d --build
    ```

2. The application will be available at `http://localhost:8000` (or the configured port).

## MCP Endpoint (remote control for bots/agents)

The app serves an [MCP](https://modelcontextprotocol.io) server at `/mcp`, protected by OAuth 2.1. Point any MCP client that supports remote servers with OAuth (Claude, Claude Code, etc.) at `https://block.mydomain.com/mcp`. The client discovers the OAuth endpoints, registers itself, and opens a browser where you log in with your normal app account and click **Allow**.

Tools: `list_rules`, `set_rule`, `set_all_rules` (Block/Unblock All), `refresh_rules`, `list_schedules`, `set_schedule`. A rule being *enabled* means that device's internet is blocked.

Clients register themselves, but a self-registered client can only use the browser login flow, so nothing gets access without someone clicking **Allow**.

Requirements:
- Migrations run automatically when the Docker container starts (or run `python manage.py migrate` yourself outside Docker).
- Nginx has to forward the scheme and host so OAuth URLs come out as `https`:
  ```nginx
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto $scheme;
  ```

Approved clients and their tokens are listed under **Django OAuth Toolkit** in `/admin/`. Delete an application there to revoke its access. For a headless bot that can't open a browser, create an application in the admin with grant type *Client credentials* and use its client ID and secret at `/o/token/` to get a token.

## Environment Variables

Ensure the following environment variables are set in a `.env` file:
- See [`.env-example`](.env-example)

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contributing

Contributions are welcome! Please submit a pull request or open an issue for any changes or suggestions.