# debug_print.py
import inspect
from pathlib import Path

# Active/désactive les prints de debug
debug_mode = True

# Dictionnaire global pour suivre combien de fois chaque message a été affiché
_debug_counters = {}

def debug_print(msg: str, *args, max_print: int = None, **kwargs):
    """
    Affiche un message de debug avec informations sur l'appelant.
    
    Args:
        msg (str): Message principal à afficher
        *args: Variables à afficher avec leur type
        max_print (int, optional): Nombre maximum d'affichages pour ce message (None = illimité)
        **kwargs: Arguments supplémentaires passés à print
    """
    if not debug_mode:
        return

    # Compteur pour ce message
    counter_key = msg
    if counter_key not in _debug_counters:
        _debug_counters[counter_key] = 0

    if max_print is not None and _debug_counters[counter_key] >= max_print:
        return

    _debug_counters[counter_key] += 1

    # Info sur l'appelant
    frame = inspect.currentframe().f_back
    func_name = frame.f_code.co_name
    line_no = frame.f_lineno
    filename = frame.f_code.co_filename.split("\\")[-1]

    # Préparer le message principal
    output = f"[DEBUG] {filename}:{func_name}:{line_no} → {msg}"

    # Ajouter les variables avec leur type
    if args:
        vars_info = ", ".join(f"{repr(a)} (type={type(a).__name__})" for a in args)
        output += " | Vars: " + vars_info

    print(output, **kwargs)

def _debug_return(p: Path) -> Path:
    debug_print(f"Fichier trouvé : {p.name}")
    return p
