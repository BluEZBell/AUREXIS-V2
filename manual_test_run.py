import asyncio
import sys

def main():
    import test_alpha_harvester
    from unittest.mock import MagicMock
    
    class DummyMonkeypatch:
        def setattr(self, obj, name, value=None):
            if isinstance(obj, str):
                import importlib
                mod_name, func_name = obj.rsplit('.', 1)
                mod = importlib.import_module(mod_name)
                setattr(mod, func_name, value)
            else:
                setattr(obj, name, value)
    
    async def run_tests():
        try:
            print("Running test_alpha_harvester_free_roll...")
            await test_alpha_harvester.test_alpha_harvester_free_roll(DummyMonkeypatch())
            print("test_alpha_harvester_free_roll PASSED")
            
            print("Running test_alpha_harvester_exhaustion...")
            await test_alpha_harvester.test_alpha_harvester_exhaustion(DummyMonkeypatch())
            print("test_alpha_harvester_exhaustion PASSED")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run_tests())

if __name__ == "__main__":
    main()
