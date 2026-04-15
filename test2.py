



def a(*args, **kwargs):
    f={
        "type": 1,
        **kwargs
    }
    print(f) 

a(a=2,fff=3)