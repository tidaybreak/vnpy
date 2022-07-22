source ~/.bash_profile
temp_path=$(dirname "$0")
cd $temp_path
real_path=$(pwd)
echo  "本脚本文件所在目录路径是: $real_path "
cd $real_path


time1=$(date "+%Y%m%d-%H%M%S")
server="frp.ofidc.com"


rsync(){
    exclude_list=''
    if [ -f $1"exclude.list" ]; then
      exclude_list="--exclude-from="$1"exclude.list"
      echo $exclude_list
    fi

    /usr/bin/rsync -azp --delete --exclude-from="exclude.list" $exclude_list -e 'ssh -p 51022' $1 root@$server:$2

}

rsync /home/ti/code/vnpy/ /home/ti/code/vnpy
