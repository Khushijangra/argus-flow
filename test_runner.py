import sys
import traceback

sys.path.insert(0, ".")

print("1")
try:
    print("2")
    import scripts.run_real_incident_test
    print("3")
    scripts.run_real_incident_test.run_test()
    print("4")
except Exception as e:
    with open("error.txt", "w") as f:
        f.write(traceback.format_exc())
