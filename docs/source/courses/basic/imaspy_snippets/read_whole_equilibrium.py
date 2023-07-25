from importlib_resources import files

import imaspy

# Open input datafile
shot, run, user, database = 134173, 106, "public", "ITER"
input = imaspy.DBEntry(imaspy.ids_defs.ASCII_BACKEND, database, shot, run)
assets_path = files(imaspy) / "assets/"
input.open(options=f"-prefix {assets_path}/")

# 1. Read and print the time of the equilibrium IDS for the whole scenario
# This explicitly converts the data from the old version on disk, to the
# new version of the environment that you have loaded!
equilibrium = input.get("equilibrium")  # All time slices
print(equilibrium.time)

# 2. Read and print the electron temperature profile in the core_profiles IDS
# at time slice t=433s
core_profiles = input.get("core_profiles")
print(core_profiles.profiles_1d[1].electrons.temperature)

# Close input datafile
input.close()
