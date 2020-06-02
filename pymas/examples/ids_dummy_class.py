import sys
import os

from IPython import embed
import numpy
import numpy as np


if __name__ == '__main__':
    from pymas.ids_classes import *
    # MVP, get a slice
    # So for example be able to run
    # import pymas as imas
    # input = imas.ids(shot,run_in)
    # input.open_env(input_user_or_path,input_database,’3’)
    # input.equilibrium.getSlice(time_slice, 1)

    # Existing workflow example
    shot               = 130012
    run_in             = 1
    #input_user_or_path = 'public'
    input_database     = 'iter'
    time_slice         = 200
    occurence = 0

    # Test example
    TEST_SHOT = 1
    TEST_RUN = 2
    backend = 3
    BACKEND_ID_0 = 10
    NO_BACKEND                  = BACKEND_ID_0;
    ASCII_BACKEND               = BACKEND_ID_0+1;
    MDSPLUS_BACKEND             = BACKEND_ID_0+2;
    HDF5_BACKEND                = BACKEND_ID_0+3;
    MEMORY_BACKEND              = BACKEND_ID_0+4;
    UDA_BACKEND                 = BACKEND_ID_0+5;
    backend = MDSPLUS_BACKEND
    ACCESS_PULSE_0  = 40
    FORCE_CREATE_PULSE     =     ACCESS_PULSE_0+3
    input_user_or_path = 'vandepk'
    # db_obj =  db_entry(backend, 'test', TEST_SHOT, TEST_RUN)
    # Create a new entry
    # This needs interaction with the ull
    import ual_4_7_2._ual_lowlevel as ull
    status, idx = ull.ual_begin_pulse_action(backend, shot, run_in, input_user_or_path, input_database, '3')
    if status != 0:
        raise Exception('Error calling ual_begin_pulse_action()')
    status = ull.ual_open_pulse(idx, FORCE_CREATE_PULSE, '') 
    if status != 0:
        raise Exception('Error calling ual_open_pulse()')
    db_ctx = idx 


    # Old API
    #import matplotlib.pyplot as plt
    style = 'old'
    style = 'new'
    if style == 'old':
        #import imas_3_28_1_ual_4_7_2_dev38 as imas
        import imas
        #inp_old = imas.ids(shot,run_in)
        #inp_old.open_env(input_user_or_path,input_database, '3')
        #time = inp_old.equilibrium.readTime(occurence)
        #inp_old.equilibrium.getSlice(time_slice, 1)
        #inp_old.close()
        #timeslice = inp_old.equilibrium.time_slice[0]
        #print('Using code {!s}'.format(inp_old.equilibrium.code.name))
        #print('time =', time)
        #print(timeslice.profiles_1d.psi)
        #print(timeslice.profiles_1d.b_average)
        # Other magic

        imas_entry = imas.ids(shot, run_in)
        idx = imas_entry.create_env(input_user_or_path, input_database, '3')
        ids = imas_entry.equilibrium
        #ids.ids_properties.homogeneous_time = 2-
        time = 0
        ids.ids_properties.homogeneous_time = time
        ids.setPulseCtx(db_ctx)
        ids.put()
        print('Temp database made')
        print('Original ids.ids_properties.homogeneous_time:', ids.ids_properties.homogeneous_time)
        ids.ids_properties.homogeneous_time = 'foo'
        print('Changed ids.ids_properties.homogeneous_time:', ids.ids_properties.homogeneous_time)
        ids.get()
        print('After re-get ids.ids_properties.homogeneous_time:', ids.ids_properties.homogeneous_time)
    else:
        # New API
        # 4.4.1 Initializing an empty IDS
        import pymas as imas
        idsdef_dir = os.path.join(os.path.dirname(__file__), '../../../imas-data-dictionary/')
        idsdef = os.path.join(idsdef_dir, 'IDSDef.xml')
        imas_entry = imas.ids(shot, run_in, xml_path=idsdef, verbosity=2)
        # This should then support accessing an IDS using idsVar.<IDSname>.<IDSfield>

        # 5.5 Opening an existing Data Entry
        #imas_entry.open_env(input_user_or_path, input_database, '3')

        # 5.6 Opening a remote Data Entry using the UDA backend
        #imas_entry = imas.ids(54178, 0)
        #imas_entry.open_public('WEST')

        # 5.7 Closing an opened Data Entry
        # [retstatus] = imas_entry.close()

        # 4.4.2 Copying a variable to a new IDS. Not deepcopy! Proposed API:
        # idsVar2.equilibrium.copyValues(idsVar)

        # 4.4.3 Deallocation
        # Using python build-in management, or del var

        # 5.4 Creating a new data entry
        imas_entry.create_env(input_user_or_path, input_database, '3')
        # Put mandatory top-level entry
        ids = imas_entry.equilibrium
        #ids.ids_properties.homogeneous_time = 2
        time = 0
        ids.ids_properties.homogeneous_time = time

        #thing = IDSStructure()
        ids.setPulseCtx(db_ctx)
        ids.put()
        #ids.ids_properties.homogeneous_time = 'crap'
        print('Done putting')
        print('Putting')

        #ids.get(ctx=db_ctx, homogeneousTime=time)
        print('Temp database made')
        print('Original ids.ids_properties.homogeneous_time:', ids.ids_properties.homogeneous_time)
        ids.ids_properties.homogeneous_time = 9999
        print('Changed ids.ids_properties.homogeneous_time:', ids.ids_properties.homogeneous_time)
        ids.get()
        print('After re-get ids.ids_properties.homogeneous_time:', ids.ids_properties.homogeneous_time)

        # Creating a nested data entry
        print('Pre put ids.ids_properties.version_put.access_layer:', ids.ids_properties.version_put.access_layer)
        ids.ids_properties.version_put.access_layer = 'pymas'
        ids.put()
        print('Post put ids.ids_properties.version_put.access_layer:', ids.ids_properties.version_put.access_layer)
        ids.get()
        print('Post get ids.ids_properties.version_put.access_layer:', ids.ids_properties.version_put.access_layer)

        # Deeper fields
        # Set time vector
        print('Pre put ids.time:', ids.time)
        ids.time = [0.1, 0.2, 0.3]
        ids.put()
        print('Post put ids.time:', ids.time)
        ids.time = [12345678] # Scamble
        ids.get(verbosity=2)
        print('Post get ids.time:', ids.time)

        # And an array
        print('Pre put ids.vacuum_toroidal_field.b0:', ids.vacuum_toroidal_field.b0)
        ids.vacuum_toroidal_field.b0 = [1, 2, 3]
        ids.put()
        print('Post put ids.vacuum_toroidal_field.b0:', ids.vacuum_toroidal_field.b0)
        # Scramble
        ids.vacuum_toroidal_field.b0 = [-98767890]
        ids.get()
        print('Post get ids.vacuum_toroidal_field.b0:', ids.vacuum_toroidal_field.b0)

        # We can do fancy math even!
        print('ids.vacuum_toroidal_field.b0 + 2:', ids.vacuum_toroidal_field.b0 + 2)

        ## Set beyond a struct array
        #print('Pre put ids.time_slice[0].profiles_1d.psi:', ids.time_slice[0].profiles_1d.psi)
        #ids.time_slice[0].profiles_1d.psi = [0, 0.5, 1]
        #ids.put(verbosity=2)
        #print('Post put ids.time_slice[0].profiles_1d.psi:', ids.time_slice[0].profiles_1d.psi)
        ## Scramble
        #ids.time_slice[0].profiles_1d.psi = [-98767890]
        #ids.get()
        #print('Post get ids.time_slice[0].profiles_1d.psi:', ids.time_slice[0].profiles_1d.psi)

        # time_slice.coordinate_system.grid.volume_element 2D_FLT
        # time_slice.coordinate_system.tensor_covariant 4D_FLT

        # 5.8 Putting an IDS
        # imas_entry.pf_active.put(occurence)

        # 5.9 Putting an IDS progressively in a time loop
        # Expect the IDS variable to contain a single slice in any non-empty dynamic nodes
        # So, start with a single .put, then progressive put_slice IN STRICT TIME ORDER

        # 5.10 Deleting an IDS
        # imas_entry.pf_active.deleteData(occurence)

        # 5.11 getting an IDS
        # imas_entry.pf_active.get(occurence)

        # 5.12 Getting a slice
        # imas_entry.pf_active.getSlice(0.1, 2)

        # 5.13 Getting units of a note
        # Slash-separated path, ignore arrays, as all units in array are the same
        # units = get_units(ids, node_path)

        # 5.14 Getting a subset of an IDS
        # Smart datapath, so path/to/array(idx)/field
        # Smart datapath, so path/to/array(x:y)/field
        # partialGet

        # 5.15 Selecting the backend
        # MDSPLUS, MEMORY, UDA, ASCII
        # MAGIC, ignore for now?

        # Grab a direct child node of primitive type FLT_1D. It's dynamic, so special, and a coordinate, double special
        #time = imas_entry.equilibrium.readTime(occurence)
        # Grab a child structure
        #print(time)
        #e.g. ids_entry = imas.ids(12,1)
        #inp.equilibrium.getSlice(time_slice, 1)
        #timeslice = inp.equilibrium.time_slice[0]
        # retstatus, idx = ids_entry.create_env('usr', 'test', '3')
    #plt.plot(timeslice.profiles_1d.psi, timeslice.profiles_1d.b_average)
    #plt.show()

