# Simple image for the agent service
FROM python:3.11-slim

WORKDIR /app

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime deps
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Add source
COPY agent ./agent

# Default envs (overridden by docker-compose)
ENV AGENT_ID=agent PORT=5000 PEERS=

EXPOSE 5000

CMD ["python", "-m", "agent.app"]
