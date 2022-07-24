source ~/.bash_profile
temp_path=$(dirname "$0")
cd $temp_path
real_path=$(pwd)
echo  "本脚本文件所在目录路径是: $real_path "
cd $real_path

export PYTHONPATH=$PYTHONPATH:$real_path"/.."
export PYTHONPATH=$PYTHONPATH:$real_path"/../.."
echo "export PYTHONPATH="$PYTHONPATH
#cd quant

python download_data.py
#python backtest_console.py
#python optimization_console.py
#python main_console.py $*
