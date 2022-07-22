yum install  gcc libffi-devel zlib* openssl-devel
yum install -y xz-devel bzip2-devel

cd Python-3.8.x
./configure
make -j 30
make install


mongo
use admin
db.auth("root","root")

pip install requests
pip install -U kaleido
pip install vnpy_ctastrategy==1.1.0
pip install vnpy-binance==2021.10.27
pip install vnpy-mongodb==1.0.3
pip install vnpy-rqdata==2.9.48.2
pip install openpyxl==3.0.10
pip install vnpy_sqlite



pip uninstall vnpy