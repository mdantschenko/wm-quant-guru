import wmguru 

def test_import_works():
    if wmguru is not None:
        print("OKAY")
    else:
        print("NOT OKAY")