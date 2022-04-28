# Curse of Aros (mobile MMORPG) Skills calculator
http://coa-calculator.herokuapp.com/


This is the back end of a calculator built with FastAPI(Python) to support calculating Skills XP on CoA.


## Setup:
```
python3 -m venv venv

source venv/bin/activate

export PYTHONPATH=$PWD

pip3 install fastapi

pip3 install uvicorn
```

## Run on develop server:
If venv is not activated:

`source venv/bin/activate && uvicorn src.api:app --reload`


Otherwise:

`uvicorn src.api:app --reload`

## Deploy to Heroku:
- Configure Procfile and requirements.txt
- On Heroku Dashboard select Python Buildpack
- https://www.youtube.com/watch?v=9gSkdEWx_VA
