
import datetime
import json
import os

LOG_FILE = "/app/data/audit_log.jsonl"

def log_action(question, tool_used, live_data, answer):
    """
    Logs every AI interaction to a file
    jsonl = one JSON object per line
    easy to read and parse later
    """

    entry = {
        "timestamp" : datetime.datetime.now().isoformat(),
        "question" : question,
        "tool_used" : tool_used,
        "live_data" : live_data,
        "answer" : answer[:200]
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

def read_log():
   """
    Reads the audit log and returns
    last 20 entries as a list
    """

   if not os.path.exists(LOG_FILE):
       return []

   with open(LOG_FILE, "r") as f:
       lines = f.readlines()

   entries=[]      
   
   for line in lines:
       try:
           entries.append(json.loads(line.strip()))
       except:
           pass
       

   return list(reversed(entries[-20:]))
       
    
           
       
   

 
