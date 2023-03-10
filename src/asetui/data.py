from collections import defaultdict
from dataclasses import dataclass
from typing import List, Tuple, Union

import pandas as pd
from ase.db import connect
from ase.db.core import float_to_time_string, now
from ase.db.table import all_columns
from ase import Atoms
from rich.text import Text
from textual.widgets import ListItem, Label


@dataclass
class Data:
    df: pd.DataFrame
    db_path: str
    user_keys: List[str]
    row_cache: Union[dict, None] = None
    chosen_columns: Union[List[str], None] = None

    def __post_init__(self):
        if self.row_cache is None:
            self.row_cache = {}
        self.update_chosen_columns()

    def string_df(self) -> pd.DataFrame:
        return self.df[self.chosen_columns].applymap(format_value, na_action="ignore").fillna("", axis=1)
    
    def string_column(self, column):
        return self.df[column].map(format_value, na_action='ignore').fillna("")

    def row_details(self, row) -> Tuple[Text, list]:
        """Returns key value pairs from the row in two items:"""
        static_kvps = ""
        dynamic_kvps = []
        editable_keys = self.user_keys + ["pbc"]
        for key, value in self.df.iloc[row].dropna().items():
            if key in editable_keys:
                dynamic_kvps.append(ListItem(Label(f"[bold]{key}: [/bold]{value}")))
            else:
                static_kvps += f"[bold]{key}: [/bold]{value}\n"
        return Text.from_markup(static_kvps[:-1]), dynamic_kvps
    
    def row_data(self, row: int) -> list:
        row_id = int(self.df.iloc[row].id)
        dynamic_data = []
        for key, value in get_data(self.db_path, row_id).items():
            dynamic_data.append(ListItem(Label(f"[bold]{key}: [/bold]{value}")))
        return dynamic_data
    
    def get_atoms(self, row) -> Atoms:
        db = connect(self.db_path)
        return db.get_atoms(id=int(self.df.iloc[row].id))
    
    def add_to_chosen_columns(self, column):
        if column not in self.chosen_columns and column in all_columns + self.user_keys:
            self.chosen_columns.append(column)
            # chosen_columns now contain column, return True
            return True
        # Nothing has been added return False
        return False
    
    def update_chosen_columns(self):
        # Check if db columns file exists. If so set chosen columns based on that.

        # If the db is not in the asetui columns file initialize with all_columns
        self.chosen_columns = all_columns
    
    


def format_value(val) -> Union[Text, str]:
    if isinstance(val, str):
        return val
    elif isinstance(val, float):
        if abs(val) > 1e6 or abs(val) < 1e-4:
            format_spec = "#.3g"
        else:
            format_spec = ".2f"
        return Text("{1:{0}}".format(format_spec, val), justify="right")
    elif isinstance(val, int):
        return Text(str(val), justify="right")
    else:
        return str(val)


def instantiate_data(db_path: str, sel: str = "") -> Data:
    db = connect(db_path)
    df, user_keys = db_to_df(db, sel)
    return Data(df=df, db_path=db_path, user_keys=user_keys)


def db_to_df(db, sel="") -> tuple[pd.DataFrame, List[str]]:
    """Convert a db into a pandas.DataFrame.

    The columns are built using defaultdicts, and put into a
    dataframe in the end.

    """
    cols = defaultdict(list)
    user_keys = set()
    keys = all_columns
    i = 0
    for row in db.select(selection=sel):
        # default keys are always present
        for k in keys:
            cols[k].append(get_value(row, k))
        user_keys |= set(row.key_value_pairs.keys())
        for k in user_keys:
            cols[k].extend([pd.NaT] * (i - len(cols[k])) + [get_value(row, k)])
        i += 1
    df = pd.DataFrame(cols, index=cols["id"])
    df["id"] = df["id"].astype("int")
    return df, list(user_keys)


def get_value(row, key) -> str:
    """Get the value from the row to the dataframe."""
    if key == "age":
        value = float_to_time_string(now() - row.ctime)
    elif key == "pbc":
        value = "".join("FT"[int(p)] for p in row.pbc)
    else:
        value = row.get(key, pd.NaT)
    return value

def get_data(db_path, row_id):
    db = connect(db_path)
    return db.get(id=row_id).data
    
