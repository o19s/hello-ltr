#!/bin/sh

python build_bigram_index.py 0 250000 & \
    python build_bigram_index.py 250000 500000 & \
    python build_bigram_index.py 500000 750000 & \
    python build_bigram_index.py 750000 1000000 
    
python build_bigram_index.py 1000000 1250000 & \
    python build_bigram_index.py 1250000 1500000 & \
    python build_bigram_index.py 1500000 1750000 & \
    python build_bigram_index.py 1750000 2000000 

python build_bigram_index.py 2250000 2500000 & \
    python build_bigram_index.py 2500000 2750000 & \
    python build_bigram_index.py 2750000 3000000 & \
    python build_bigram_index.py 3000000 3250000 
