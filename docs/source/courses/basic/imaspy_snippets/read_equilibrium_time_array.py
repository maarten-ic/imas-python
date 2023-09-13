import numpy as np
import imaspy.training


# Find nearest value and index in an array
def find_nearest(a, a0):
    "Element in nd array `a` closest to the scalar value `a0`"
    idx = np.abs(a - a0).argmin()
    return a.value[idx], idx


# Open input data entry
entry = imaspy.training.get_training_db_entry()
assert isinstance(entry, imaspy.DBEntry)

# Read the time array from the equilibrium IDS
eq = entry.get("equilibrium")
time_array = eq.time

# Find the index of the desired time slice in the time array
t_closest, t_index = find_nearest(time_array, 433)
print("Time index = ", t_index)
print("Time value = ", t_closest)

# Close input data entry
entry.close()
