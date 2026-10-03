import numpy as np
import pandas as pd

rates = np.array([(1, 2, 3), (4, 5, 6)], dtype=[('time', 'i4'), ('close', 'f8'), ('high', 'f8')])

if len(rates) == 0:
    print("Empty")
