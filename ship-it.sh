python3 setup.py sdist bdist_wheel
python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
#python3 -m twine upload dist/*
echo "Removing files..."
rm -rf build dist *egg-info*
echo "Done!"