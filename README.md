# Human-Tracker
Repositorio para Construcción de Sistemas de Computación

## Para crear el ejecutable
### Si existen las carpetas /dist y /build
####  (En caso de hacer cambios en los archivos .py volver a ejecutar el respectivo .spec)

#### pyinstaller analisisDatos.spec
#### pyinstaller detectarweb.spec
#### pyinstaller "Human Tracker.spec"

### Si NO existen las carpetas /dist y /build

#### pyinstaller analisisDatos.py --onefile --noconsole 
#### pyinstaller detectarweb.py --onefile --noconsole
#### pyinstaller --onefile --name "Human Tracker" --console --add-data "logo.png:." --add-data "untrefLogo.jpg:." --icon=logo.ico interfaz.py

## Para crear el ejecutable como un unico directorio, no un unico archivo 
### Si no existen las carpetas /dist y /build
#### pyinstaller interfaz.py --name="Human Tracker" --onedir --noconsole --add-data "logo.png;." --add-data "untrefLogo.jpg;." --hidden-import=detectarweb --hidden-import=analisisDatos --hidden-import=yolov10s


