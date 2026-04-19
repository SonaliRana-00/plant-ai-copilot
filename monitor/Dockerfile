FROM python:3.11-slim
WORKDIR /app
RUN pip install streamlit pandas
COPY dashboard.py .
CMD ["streamlit", "run", "dashboard.py", "--server.port=8502"]