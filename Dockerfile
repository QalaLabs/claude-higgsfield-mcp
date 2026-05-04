FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV MCP_PATH=/mcp

EXPOSE 8000

CMD ["python", "-m", "higgsfield_mcp.server"]
