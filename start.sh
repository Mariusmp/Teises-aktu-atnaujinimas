#!/bin/bash

# Nustatome kelią iki aplanko, kuriame yra šis scenarijus,
# kad jis veiktų nepriklausomai nuo to, iš kur yra paleidžiamas.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Nurodome tiesioginį kelią iki Python interpretatoriaus virtualioje aplinkoje
PYTHON_EXEC="$SCRIPT_DIR/ta_update/bin/python"

# Nurodome tiesioginį kelią iki tavo Python programos
PYTHON_SCRIPT="$SCRIPT_DIR/TA_update.py"

# Paleidžiame tavo programą su konkrečiu Python interpretatoriumi
"$PYTHON_EXEC" "$PYTHON_SCRIPT"

# Pauzė pabaigoje, kad terminalo langas neužsidarytų iškart
read -p "Programa baigė darbą. Spauskite Enter, kad uždarytumėte."
