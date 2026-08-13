FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements_server.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Verify FastMCP import during build
RUN python3 -c "from mcp.server.fastmcp import FastMCP; print('FastMCP verified in container build!')"

# Copy server code
COPY server_mcp.py .

ENV PORT=8080
EXPOSE 8080

CMD ["python3", "server_mcp.py"]
