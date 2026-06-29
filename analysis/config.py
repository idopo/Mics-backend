"""Connection settings for the MICS behavioral-analysis scripts.

Point these at the Elasticsearch instance that holds the MICS event log. Either
edit the defaults below, or override at run time with environment variables
(ES_URL / ES_INDEX) — the env vars win.

Windows examples
----------------
PowerShell:   $env:ES_URL = "http://132.77.73.125:9200"
cmd.exe:      set ES_URL=http://132.77.73.125:9200
conda (persist in the env):
              conda env config vars set ES_URL=http://132.77.73.125:9200
              conda deactivate && conda activate mics-analysis
"""
import os

# Elasticsearch host. On the analysis machine used to produce the committed
# figures this was a local tunnel (http://localhost:9200); from another machine
# on the lab network use the server that hosts the index, e.g.
# http://132.77.73.125:9200.
ES_URL = os.environ.get("ES_URL", "http://localhost:9200")

# Index containing the behavioral events.
ES_INDEX = os.environ.get("ES_INDEX", "restored-event_log_v2")
