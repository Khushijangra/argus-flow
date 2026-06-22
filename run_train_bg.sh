#!/bin/bash
source ~/.bashrc
cd "/teamspace/studios/this_studio/NEXUS-ATMS/argus_stream_extracted/argus stream A"
nohup python scripts/train.py --dataset ua_detrac --output-dir "../../outputs/ua_detrac_stream_a_run1" > "../../outputs/ua_detrac_stream_a_run1/train.log" 2>&1 &
