#!/bin/bash
celery -A udmtoggler worker --loglevel=info --beat --scheduler django
