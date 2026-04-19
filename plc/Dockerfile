FROM python:3.11-slim
WORKDIR /plc
RUN pip install opcua cryptography
COPY opcua_server.py .
EXPOSE 4840
CMD ["python", "opcua_server.py"]