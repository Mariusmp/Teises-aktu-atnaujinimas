#!/bin/bash

# Nustatome kelią iki aplanko, kuriame yra šis scenarijus,
# kad jis veiktų nepriklausomai nuo to, iš kur yra paleidžiamas.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Nurodome tiesioginį kelią iki Python interpretatoriaus virtualioje aplinkoje
PYTHON_EXEC="$SCRIPT_DIR/ta_update/bin/python"
UVICORN_EXEC="$SCRIPT_DIR/ta_update/bin/uvicorn"

# Paleidžiame FastAPI serverį fone
"$UVICORN_EXEC" app:app --host 127.0.0.1 --port 8000 &
SERVER_PID=$!

# Palaukiame kelias sekundes, kol serveris užsikraus
sleep 3

# Atidarome naršyklę
if which xdg-open > /dev/null
then
  xdg-open http://127.0.0.1:8000/
elif which open > /dev/null
then
  open http://127.0.0.1:8000/
else
  echo "Nepavyko automatiškai atidaryti naršyklės. Prašome atidaryti http://127.0.0.1:8000/ rankiniu būdu."
fi

# Pauzė pabaigoje, kad terminalo langas neužsidarytų iškart.
# Serveris liks veikti, kol šis langas bus uždarytas.
echo "Serveris veikia. Norėdami sustabdyti, uždarykite šį langą arba paspauskite Ctrl+C."
wait $SERVER_PID
