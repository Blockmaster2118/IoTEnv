#!/bin/bash

while true; do
  echo 'LOCK:1234' | nc 192.168.50.20 9999
  sleep 2
done