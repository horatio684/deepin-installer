#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2012~2013 Deepin, Inc.
#               2012~2013 Long Wei
#
# Author:     Long Wei <yilang2007lw@gmail.com>
# Maintainer: Long Wei <yilang2007lw@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

TARGET="/target"
PART_TYPE_LIST=["primary","logical","extend","freespace","metadata","protect"]
import os
from basic_utils import run_os_command,get_os_command_output
import parted
from log_util import LogUtil

class PartUtil:
    '''user interface communicate with backend via disk_partition_info_tab,mark each partition in the table:
    keep:the origin partition,we don't want and don't need to change
    add:new added partition,we should do add partition
    delete:to added partition,just remove from the table;else mark delete flag,then do real delete operation
    '''
    def __init__(self):
    #for temporay used variable    
        self.device=""
        self.devices=[]
        self.disk=""
        self.disks=[]
        self.partition=""
        self.partitions=[]
    #{dev_path:disk}
        self.path_disks=self.__get_path_disks()
    #{disk:[partition1,partition2,],disk2:[]}
        self.path_disks_partitions=self.__get_path_disks_partitions()
    #{disk:[ partition,part_type,part_size,part_fs,
    #        part_format,part_name,part_mountpoint,part_location,part_flag
    #      ]
    #}
        self.disk_partition_info_tab=self.init_disk_partition_info_tab()
        #{disk:{partition:part_path}}
        self.disk_part_display_path=self.init_disk_part_display_path()




    #get disk space_info,used in display available size and constraint the new creating partition size    
    # {disk:[   [main_part_list,logical_part],
    #           [main_geom_list,logical_geom_list],
    #           [main_geom_gap_list,logical_geom_gap_list]
    #       ],
    #    
    #  }   
        self.disk_space_info_tab={}




        self.lu=LogUtil()
        self.logger=self.lu.create_logger("part_logger","debug")
        self.handler=self.lu.create_logger_handler(self.logger,"file","debug","lineno",None)

        self.backup_disk_partition_info_tab=self.init_backup_disk_partition_info_tab()
        # self.backup_disk_partition_info_tab=copy.deepcopy(self.disk_partition_info_tab)


    #######################fill in data relative to disk#######################
    def __get_path_disks(self):
        '''return{ path:disk} dict,called this only once to make sure the Ped object id will not change'''
        self.path_disks={}
        self.devices=parted.getAllDevices()
        for device in self.devices:
            if "/dev/sd" in device.path or "/dev/hd" in device.path:
                try:
                    self.disk=parted.disk.Disk(device,None)
                except:
                    self.disk=self.set_disk_label(device)
                self.path_disks[device.path]=self.disk   

        return self.path_disks

    def __get_path_disk_partitions(self,disk):
        '''return [partition],only called by __get_path_disks_partitons'''
        partitions = []
        partition = disk.getFirstPartition()
        while partition:
            if partition.type & parted.PARTITION_FREESPACE or \
               partition.type & parted.PARTITION_METADATA or \
               partition.type & parted.PARTITION_PROTECTED:
                partition = partition.nextPartition()
                continue
            partitions.append(partition)
            partition = partition.nextPartition()

        return partitions

    def __get_path_disks_partitions(self):
        '''return {disk:[partition1,partition2],disk2:[partition1]},calld this only once to keep Ped partition id uniquee'''
        path_disks_partitons={}
        for disk in self.get_system_disks():
            path_disks_partitons[disk]=self.__get_path_disk_partitions(disk)
            
        return path_disks_partitons    

    def get_install_device_info(self):
        '''return dict {/dev/sda:size,/dev/sdb:size} to choose which to install linux deepin'''
        self.devices=parted.getAllDevices()
        self.install_info={}
        for device in self.devices:
            if "/dev/sd" in device.path or "/dev/hd" in self.device.path:
                dev_path=device.path
                dev_size=str(device.getSize(unit="GB"))+"GB"
                self.install_info[dev_path]=dev_size

        return self.install_info

    def get_system_disks(self):
        '''return list of system disks,fetch the global path_disks'''
        self.disks=[]
        for item in self.path_disks.values():
            self.disks.append(item)
        return self.disks    

    def get_disk_from_path(self,dev_path):
        '''from path:/dev/sda to get disk,fetch the global path_disks need to keep the only Ped id'''
        if dev_path in self.path_disks.keys():
            return self.path_disks[dev_path]
        else:
            print "there's no disk specified by the path"
            self.lu.do_log_msg(self.logger,"critical","there's no disk specified by the path")
            return None

    def get_device_from_path(self,dev_path):
        '''from path:/dev/sda to get device,old function,avoid to use this'''
        return parted.device.Device(dev_path,None)

    def get_disk_size(self,disk):
        '''get disk size,used to compare with the optimize swap size'''
        return disk.device.getSize("MB")

    def get_disk_max_primary_count(self,disk):
        '''return max primary NO. the disk can hold '''
        self.max_primary_count=disk.MaxPrimaryPartitionCount()
        if len(self.max_primary_count)==0:
            self.max_primary_count=4
        return self.max_primary_count    

    def get_disk_max_support_count(self,disk):
        '''return max support NO. the disk can hold'''
        self.max_support_count=disk.maxSupportedPartitionCount()
        return self.max_support_count

    def get_disk_primary_list(self,disk):
        '''return list of disk primary partitions,not include marked delete'''
        disk_primary_list=[]
        for item in filter(lambda info:info[-1]!="delete",self.disk_part_info_tab[disk]):
            if item[1]=="primary" or item[0].type==0:
                disk_primary_list.append(item)

        return disk_primary_list                        

    def get_disk_logical_list(self,disk):
        '''return list of disk logical partitions,not include marked delete'''
        disk_logical_list=[]
        for item in filter(lambda info:info[-1]!="delete",self.disk_part_info_tab[disk]):
            if item[1]=="logical" or item[0].type==1:
                disk_logical_list.append(item)
        return disk_logical_list

    def get_disk_extend_list(self,disk):
        '''return list of disk extend partitions,not include marked delete'''
        disk_extend_list=[]
        for item in filter(lambda info:info[-1]!="delete",self.disk_part_info_tab[disk]):
            if item[1]=="extend" or item[0].type==2:
                disk_extend_list.append(item)
        return disk_extend_list

    ##################disk->partiton structure,in logical concept,not react to the physical disk################
    def get_disk_partitions(self,disk):
        '''return partitions of the given disk,get value from path_disks_partitions'''
        return self.path_disks_partitions[disk]

    def get_disk_partition_mount(self,partition):
        '''get partition mount info,need consider multiple mount '''
        mountinfo=[]
        try:
            part_path=partition.path
            mtab=get_os_command_output("cat /etc/mtab")
            for item in mtab:
                if item.startswith(part_path):
                    mountinfo.append(item.split())
        except:
            print "cann't get mount info"
        return mountinfo        

    def get_disk_main_partitions(self,disk):
        '''get primary and extended part list,attention:not include marked delete part'''
        return filter(lambda item:item[-1]!="delete" and item[0].disk==disk 
                                and (item[0].type ==0 or item[0].type==2),self.disk_partition_info_tab)

    def get_disk_primary_partitions(self,disk):
        '''get primary part list'''

        return filter(lambda item:item[-1]!="delete" and item[0].disk==disk 
                                and (item[0].type ==0),self.disk_partition_info_tab)

    def get_disk_extended_partition(self,disk):
        '''return extended partition of the disk'''

        return filter(lambda item:item[-1]!="delete" and item[0].disk==disk 
                                and (item[0].type ==2),self.disk_partition_info_tab)


    def get_disk_logical_partitions(self,disk):
        '''get disk logical part list'''

        return filter(lambda item:item[-1]!="delete" and item[0].disk==disk 
                                and (item[0].type ==1),self.disk_partition_info_tab)

    #disk_partition_tab && disk_partition_info operations:
    def init_disk_partition_info_tab(self):
        '''read origin disk partition info'''
        disk_partition_info_tab={}
        disk_partition_info_tab_item=[]

        for disk in self.get_system_disks():
            disk_partition_info_tab[disk]=[]

            if disk.getFirstPartition()==None:
                self.set_disk_label(disk.device)
                continue 
            for part in self.get_disk_partitions(disk):
                part_type=PART_TYPE_LIST[part.type]
                part_size=part.getSize(unit="MB")
                try:
                    part_fs=part.fileSystem.type#just for primary and logical partition
                except:
                    part_fs=None
                part_format=False#donn't format origin partition
                try:
                    part_name=part.name
                except:
                    part_name=""
                try:
                    part_mountpoint=self.get_disk_partition_mount(part)[0][1]
                except:
                    part_mountpoint=""
                part_location="start"#start/end
                part_flag="keep"   #flag:keep,new,delete 

                disk_partition_info_tab_item=[part,part_type,part_size,part_fs,part_format,
                                              part_name,part_mountpoint,part_location,part_flag]

                disk_partition_info_tab[disk].append(disk_partition_info_tab_item)

        return disk_partition_info_tab

    def init_disk_part_display_path(self):
        '''display_path for vitual path to display in UI listview'''
        disk_part_display_path={}
        for disk in self.get_system_disks():
            disk_part_display_path[disk]={}
            for part in self.get_disk_partitions(disk):
                disk_part_display_path[disk][part]=part.path

        return disk_part_display_path       

    ##############update path_disks_partitons structure when add/delete partition##################

    def insert_path_disks_partitions(self,disk,partition):
        '''insert new added partition to path_disk_partitions variable,keep partition id uniquee'''
        if disk.getPedDisk!=partition.disk.getPedDisk:
            print "the partition(id) not in the disk(id)"
            self.lu.do_log_msg(self.logger,"error","somewhere id not match")
        self.path_disks_partitions[disk].append(partition)    

    def delete_path_disks_partitions(self,disk,partition):
        '''delete partition from path_disks_partitions variable,keep partition id uniquee'''
        if disk.getPedDisk!=partition.disk.getPedDisk:
            print "the partition(id) not in the disk(id)"
            self.lu.do_log_msg(self.logger,"error","somewhere id not match")
        self.path_disks_partitions[disk].remove(partition)

    def rebuild_disk_partition_info_tab(self,disk):
        '''backend operation for UI:create new disk partition tab'''
        self.disk_partition_info_tab[disk].clear()
        self.disk_part_display_path[disk].clear()        
            
    def recovery_disk_partition_info_tab(self,disk):
        '''backend operation for UI:recovery edited disk partition tab'''
        #init disk_partition_info_tab
        del self.disk_partition_info_tab[disk]
        self.disk_partition_info_tab[disk]=[]

        for item in self.backup_disk_partition_info_tab[disk]:
            item_list=[]
            for i in item:
                item_list.append(i)
            self.disk_partition_info_tab[disk].append(item_list)    

        #init disk_part_display_path        
        if disk in self.disk_part_display_path.keys():
            self.disk_part_display_path[disk].clear()
            del self.disk_part_display_path[disk]
        self.disk_part_display_path[disk]={}    
        for part in self.get_disk_partitions(disk):
            self.disk_part_display_path[disk][part]=part.path

    def set_disk_label(self,device):
        '''set disk label:gpt or msdos,for blank disk'''
        if device.getSize() >= 1.5*1024*1024:
            self.disk=parted.freshDisk(device,"gpt")
        else:
            self.disk=parted.freshDisk(device,"msdos")
            
        return self.disk

    def init_backup_disk_partition_info_tab(self):
        '''copy from init_disk_partition_info_tab,as _Ped object not support simply deepcopy'''
        disk_partition_info_tab={}
        disk_partition_info_tab_item=[]

        for disk in self.get_system_disks():
            disk_partition_info_tab[disk]=[]

            if disk.getFirstPartition()==None:
                self.set_disk_label(disk.device)
                continue 
            for part in self.get_disk_partitions(disk):
                part_type=PART_TYPE_LIST[part.type]
                part_size=part.getSize(unit="MB")
                try:
                    part_fs=part.fileSystem.type#just for primary and logical partition
                except:
                    part_fs=None
                part_format=False#donn't format origin partition
                try:
                    part_name=part.name
                except:
                    part_name=""
                try:
                    part_mountpoint=self.get_disk_partition_mount(part)[0][1]
                except:
                    part_mountpoint=""
                part_location="start"#start/end
                part_flag="keep"   #flag:keep,new,delete 

                disk_partition_info_tab_item=[part,part_type,part_size,part_fs,part_format,
                                              part_name,part_mountpoint,part_location,part_flag]

                disk_partition_info_tab[disk].append(disk_partition_info_tab_item)

        return disk_partition_info_tab

    def get_disk_partition_size(self,partition):
        '''return partition size'''
        return partition.getSize("MB")

    # def get_disk_partition_object(self,disk,part_type,part_size,part_fs,part_location):
    #     '''get partition_object for add to the disk_partition_info_tab,also for actual partition add operation'''

    #     self.disk=disk
    #     self.type=self.set_disk_partition_type(self.disk,part_type)

    #     import math
    #     minlength=math.floor((part_size*1024*1024)/(self.disk.device.sectorSize)+1)
        
    #     self.free_geometry=self.get_disk_free_geometry(self.disk,part_type,minlength)
    #     # self.free_geometry=self.get_disk_free_geometry(self.disk,part_type)

    #     self.geometry=self.set_disk_partition_geometry(self.disk,self.free_geometry,part_size)

    #     self.fs=parted.filesystem.FileSystem(part_fs,self.geometry,False,None)
    #     self.partition=parted.partition.Partition(self.disk,self.type,self.fs,self.geometry,None)
    #     #track the Partition ped id
    #     self.insert_path_disks_partitions(self.disk,self.partition)
        
    #     return self.partition



    ##########operate disk_partition_info_tab,these support interface for UI##############
    def add_disk_partition_info_tab(self,disk,part_type,part_size,part_fs,part_format,part_name,part_mountpoint,part_location):
        '''add partition to the table,insert_path_disks_partitions in get_disk_partition_object because it's used
        not only for add_disk_partition_info_tab,but also the real add partition operate'''
        self.to_add_partition=self.get_disk_partition_object(disk,part_type,part_size,part_fs,part_location)

        if self.to_add_partition==None:
            print "partition is null"
            return 
        part_flag="add"   
        disk_partition_info_tab_item=[self.to_add_partition,part_type,part_size,part_fs,part_format,
                                      part_name,part_mountpoint,part_location,part_flag]
        self.disk_partition_info_tab[disk].append(disk_partition_info_tab_item)

        return self.disk_partition_info_tab

    def mark_disk_partition_info_tab(self,part,part_flag):
        '''part_flag:keep,add,delete,according the flag to adjust the disk_partition_info_tab
           Then I can do partition add delete without bother the existed partition
        '''
        if(part==None):
            print "partition doesn't exist"
            self.lu.do_log_msg(self.logger,"error","partition doesn't exist")
        for item in self.disk_partition_info_tab[part.disk]:
            if item[0]==part:
                item[-1]=part_flag
            else:
                continue

        return self.disk_partition_info_tab

    def delete_disk_partition_info_tab(self,part):
        '''for origin partition,marked delete;for to added partition,rm from the table;'''
        if(part==None):
            print "partition doesn't exist"
            return

        for item in self.disk_partition_info_tab[part.disk]:
            if item[0]==part and item[-1]=="add":
                self.disk_partition_info_tab[part.disk].remove(item)
                self.delete_path_disks_partitions(part.disk,part)
            elif item[0]==part and item[-1]=="keep":
                self.mark_disk_partition_info_tab(part,"delete")
            else:
                print "invalid,if partition marked delete,you wonn't see it"
                self.lu.do_log_msg(self.logger,"error","invalid,if partition marked delete,you wonn't see it ")
                break

        return self.disk_partition_info_tab

    def probe_tab_disk_has_extend(self,disk):
        '''probe extend partition,for except handle add logical without extend'''
        Flag=False
        for item in self.disk_partition_info_tab[disk]:
            if item[0].type==parted.PARTITION_EXTENDED or item[1]=="primary":
                Flag=True
            else:
                continue
        return Flag    

    ################set disk partition attribute before add or modify########################
    def set_disk_partition_type(self,disk,part_type):
        '''check the to added partition type,need consider the count of primary,extend,etc...'''
        if part_type=="primary":
            self.type=parted.PARTITION_NORMAL
        elif part_type=="extend":
            self.type=parted.PARTITION_EXTENDED
        elif part_type=="logical":
            self.type=parted.PARTITION_LOGICAL
        else:
            print "part type error"
            self.lu.do_log_msg(self.logger,"error","part type error")
        return self.type    

    # def set_disk_partition_geometry(self,disk,free_geometry,size):
    #     '''to get free_geometry'''
    #     if free_geometry==None:
    #         free_geometry=disk.getFreeSpaceRegions()[0]#this have to be fixed
    #     self.start=free_geometry.start
    #     self.length=long(free_geometry.length*size/free_geometry.getSize())
    #     self.end=self.start+self.length-1
        
    #     if self.end > free_geometry.end:
    #         self.end=free_geometry.end
    #         self.length=self.end-self.start+1

    #     self.geometry=parted.geometry.Geometry(disk.device,self.start,self.length,self.end,None)
    #     return self.geometry

    def set_disk_partition_name(self,partition,part_name):
        '''cann't set this attribute,need to fix'''
        if not partition.disk.supportsFeature(parted.DISK_TYPE_PARTITION_NAME):
            print "sorry,can't set partition name"
            self.lu.do_log_msg(self.logger,"warning","sorry,conn't set partition name")
        elif part_name==None or len(part_name)==0:
            partition.name=""
        else:
            partition.name=part_name

    def set_disk_partition_fstype(self,partition,fstype):
        '''format the partition to given fstype,not create the parted fs object'''
        if partition.type!=parted.PARTITION_NORMAL and partition.type!=parted.PARTITION_LOGICAL:
            print "you can only set filesystem for primary and logical partition"
            self.lu.do_log_msg(self.logger,"error","can only set fs for primary/logical partition")
            return

        for item in self.disk_partition_info_tab[partition.disk]:
            if item[0]==partition and item[4]==False:
                print "no need to format the partition"
                return 
        if fstype==None or len(fstype)==0:
            print "no filesystem specified"
            self.lu.do_log_msg(self.logger,"error","no filesystem specified")
            return

        part_path=partition.path
        #swapoff the partition before change filesystem,if not work,simply reduce code
        try:
            origin_fs_type=partition.fileSystem.type
            if origin_fs_type==fstype:
                # print "filesystem not changed"
                self.lu.do_log_msg(self.logger,"warning","filesystem not changed")
                return
            elif origin_fs_type=="linux-swap":
                swap_data=get_os_command_output("grep "+part_path+" /proc/swaps")
                if len(swap_data)!=0:
                    swap_off_command="sudo swapoff "+part_path
                    run_os_command(swap_off_command)
                else:    
                    print "swap not on"
        except:
            print "get origin_fs_type error"
            self.lu.do_log_msg(self.logger,"error","get origin_fs_type error")

        #set fstype
        if fstype=="linux-swap":
            format_command="sudo mkswap "+part_path
        elif fstype=="fat32":
            format_command="sudo mkfs.vfat "+part_path
        elif fstype in ["ext2","ext3","ext4","reiserfs","xfs","ntfs"]:
            format_command="sudo mkfs."+fstype+" -f "+part_path
        else:
            # print "invalid fstype"
            self.lu.do_log_msg(self.logger,"error","invalid fstype")
        try:    
            run_os_command(format_command)
        except:
             #umount a partition before format it to make a filesystem
            self.set_disk_partition_umount(partition)
            run_os_command(format_command)

        if fstype=="swap":
            swap_command="sudo swapon "+part_path
            run_os_command(swap_command)

    def set_disk_partition_mount(self,partition,fstype,mountpoint):
        '''mount partition to mp:new or modify,need consider various situation'''
        if mountpoint==None or len(mountpoint)==0:
            print "need mountpoint,not given"
            self.lu.do_log_msg(self.logger,"error","need mountpoint,not given")
            return 
        if partition.type==parted.PARTITION_EXTENDED:
            print "cann't mount extended partition"
            self.lu.do_log_msg(self.logger,"error","cann't mount extended partition")
            return
        part_path=partition.path
        mp=TARGET+mountpoint
        if not os.path.exists(mp):
            mkdir_command="sudo mkdir -p "+mp
            run_os_command(mkdir_command)
        if not os.path.exists(part_path):
            print "partition not exists,commit to os first"
            self.lu.do_log_msg(self.logger,"error","partition not exists,commit to os first")
            return 
        mount_command="sudo mount -t "+fstype+" "+part_path+" "+mp
        run_os_command(mount_command)
        
    def set_disk_partition_umount(self,partition):
        '''umount the partition,may used before remove a partition'''
        part_path=partition.path
        mount_flag=False
        mtab=get_os_command_output("cat /etc/mtab")
        umount_command="sudo umount "+part_path
        umount_busy_command="sudo umount -l "+part_path
        # umount_busy_command="sudo fuser -mk "+part_path
        for item in mtab:
            if item.startswith(part_path):
                mount_flag=True
            else:
                continue
        if mount_flag==True:        
            if partition.busy:
                run_os_command(umount_busy_command)
                # run_os_command(umount_command)
            else:
                run_os_command(umount_command)
        else:
            print "don't need to umount"+part_path
            return

    def set_disk_partition_flag(self,partition,flag,state):
        '''set the partition status to state'''
        if flag not in partition.getFlagsAsString():
            print "flag invalid"
            self.lu.do_log_msg(self.logger,"warning","flag invalid")
        if not partition.isFlagAvailable():
            print "flag not available"
            self.lu.do_log_msg(self.logger,"warning","flag not available")
        else:    
            if state=="on" | state=="True":
                partition.setFlag()
            else:
                partition.unsetFlag()


    #####################backend operation for add/delete partition###########################
    def delete_disk_partition(self,disk,partition):
        '''atom function:delete the given partition,called only because need delete original partition'''
        self.partitions=self.get_disk_partitions(disk)
        if partition not in self.partitions:
            print "partition not in the disk"
            self.lu.do_log_msg(self.logger,"error","partition not in the disk")
            return
        if partition.type==parted.PARTITION_EXTENDED and disk.getLogicalPartitions()!=[]:
            print "need delete all logical partitions before delete extend partition"
            self.lu.do_log_msg(self.logger,"info","delete logical partitions before delete extend")
            for logical_part in disk.getLogicalPartitions():
                self.delete_path_disks_partitions(disk,logical_part)
                
                self.disk_partition_info_tab=filter(lambda info:info[0]!=logical_part,self.disk_partition_info_tab[disk])
                try:
                    self.set_disk_partition_umount(logical_part)
                    disk.deletePartition(logical_part)
                except:
                    print "delete logical_part failed"
                    self.lu.do_log_msg(self.logger,"error","delete logical_part failed")
        self.delete_path_disks_partitions(disk,partition)    
        self.disk_partition_info_tab=filter(lambda info:info[0]!=partition,self.disk_partition_info_tab[disk])
        try:
            self.set_disk_partition_umount(partition)
            disk.deletePartition(partition)
        except:
            print "delete partition error occurs"
            self.lu.do_log_msg(self.logger,"error","delete partition error occurs")
        disk.commit()

    def delete_custom_partition(self):
        '''batch delete origin disk partitions:'''
        for disk in self.get_system_disks():
            for item in filter(lambda info:info[-1]=="delete",self.disk_partition_info_tab[disk]):
                if item[0]==None:
                    print "partition doesn't exist"
                    self.lu.do_log_msg(self.logger,"warning","partition doesn't exist")
                else:
                    try:
                        self.delete_disk_partition(disk,item[0])
                    except:
                        print "batch delete origin partition error!"

    def add_disk_partition(self):
        '''atom function:add disk partition'''
        pass
                
    def add_custom_partition(self):
        '''batch add partition according to disk_partition_info_tab,then mount them,every disk batch commit'''
        for disk in self.get_system_disks():
            for item in filter(lambda info:info[-1]=="add",self.disk_partition_info_tab[disk]):
                if item[0].type==parted.PARTITION_LOGICAL and not self.probe_tab_disk_has_extend(disk):
                    print "can't add logical partition as there is no extended partition"
                    self.lu.do_log_msg(self.logger,"error","can't add logical as no extended")
                    break
                else:
                    self.partition=item[0]
                    self.geometry=self.partition.geometry
                    self.constraint=parted.constraint.Constraint(exactGeom=self.geometry)
                    disk.addPartition(self.partition,self.constraint)
            disk.commit()        
            #mkfs/setname/mount disk partitions
            for item in filter(lambda info:info[-1]=="add",self.disk_partition_info_tab[disk]):
                if item[0].type==parted.PARTITION_LOGICAL and not self.probe_tab_disk_has_extend(disk):
                    print "as no extended partition to add logical,no need to mkfs and mount"
                    break
                else:
                    self.partition=item[0]
                    self.part_fs=item[4]
                    self.part_name=item[6]
                    self.part_mountpoint=item[7]
                    self.set_disk_partition_fstype(self.partition,self.part_fs)
                    self.set_disk_partition_name(self.partition,self.part_name)
                    self.set_disk_partition_mount(self.partition,self.part_fs,self.part_mountpoint)

    ################################auto partition tools################################
    def get_memory_total(self):
        '''get physical total memory size,unit:MB'''
        memory_total_command="grep MemTotal /proc/meminfo"
        total_size=get_os_command_output(memory_total_command)
        if len(total_size)==0:
            # print "cann't get the size of total memory"
            self.lu.do_log_msg(self.logger,"error","cann't get the size of total memory")
        else:
            self.total_memory=int(filter(lambda c:c in "0123456789.",total_size[0]))

        return self.total_memory/1024

    def if_need_swap(self):
        '''decide whether to make a swap,only used in auto partition'''
        self.total_memory=self.get_memory_total()
        self.need_swap=False
        if self.total_memory < 1024:
            self.need_swap=True

        return self.need_swap    

    def adapt_autoswap_size(self,disk):
        '''get the optimize size of the swap'''
        if self.if_need_swap()==False:
            # print "no need to make swap"
            self.lu.do_log_msg(self.logger,"warning","no need to make swap")
        else:    
            self.total_memory=self.get_memory_total()
            self.disk_size=self.get_disk_size(disk)
            if self.disk_size < 40*1024:
                self.swap_size=self.total_memory
            else:
                self.swap_size=self.total_memory*2
                
        return self.swap_size    

    def auto_partition(self,disk_path):
        '''auto partition,use a single disk,ignore the variety info tab,force format'''
        self.disk=self.get_disk_from_path(disk_path)
        self.disk_size=self.get_disk_size(self.disk)
        self.total_memory=self.get_memory_total()
        #delete all partition first,the path_disks_partitions,disk_partition_info_tab automatic sync
        for part in self.get_disk_partitions[self.disk]:
            self.delete_disk_partition(self.disk,part)

        if self.if_need_swap:
            self.swap_size=self.adapt_autoswap_size(self.disk)
            self.add_disk_partition_info_tab(disk_path,"primary",self.swap_size,"linux-swap",None,None,None)

        if self.disk_size > 40*1024:
            self.add_disk_partition_info_tab(disk_path,"primary",5*1024,"ext4",None,None,"/")
            self.add_disk_partition_info_tab(disk_path,"primary",self.disk_size-self.swap_size-5*1024,"ext4",None,None,"/home")
        else:
            self.add_disk_partition_info_tab(disk_path,"primary",self.disk_size-self.swap_size,"ext4",None,None,"/")
            
        self.add_custom_disk_partition(self.disk_partition_info_tab)





    ##################old get disk freespace geometry function#############################
    def get_disk_free_space_info(self):
        '''basic function help for get available size to UI,not really in the disk:
           get_disk_free_geometry
           get_disk_single_available_space_size
           get_disk_total_available_space_size
        '''
    #get disk space_info,used in display available size and constraint the new creating partition size    
    # {disk:[   [main_part_list,logical_part],
    #           [main_geom_list,logical_geom_list],
    #           [main_geom_gap_list,logical_geom_gap_list]
    #       ],
    #    
    #  }   
        self.disk_space_info_tab={}
        for disk in self.get_system_disks():
            self.primary_part=[]
            self.extended_part=[]
            self.extend_part=""
            self.main_part_list=[]
            self.logical_part=[]
            self.main_geom_list=[]
            self.logical_geom_list=[]   
            self.main_geom_gap_list=[]
            self.logical_geom_gap_list=[]
            self.disk_space_info_list=[[],[],[]]
            
        #get disk main_part_list and logical_part,#fix:use space now in the to deleted part
            # for item in filter(lambda info:info[0].disk==disk,self.disk_partition_info_tab):
            for item in filter(lambda info:info[0].disk==disk and info[-1]!="delete",self.disk_partition_info_tab):
                if item[2]=="primary":
                    self.primary_part.append(item[0])
                    continue
                elif item[2]=="logical":
                    self.logical_part.append(item[0])
                    continue
                elif item[2]=="extend":
                    self.extended_part.append(item[0])
                    continue
                else:
                    print "invalid part type"
                    self.lu.do_log_msg(self.logger,"warning","invalid part type")
                    continue

            if len(self.extended_part)>1:        
                print "can have only one extended_part"
                self.lu.do_log_msg(self.logger,"error","can have only one extended_part")
            elif len(self.extended_part)==0:
                self.logger.info("the disk doesn't have extended_part")
                print "the disk "+disk.device.path+" doesn't have extended_part"
            else:
                self.extend_part=self.extended_part[0]
        
            if len(self.primary_part)!=0:
                self.main_part_list=filter(lambda item:item in self.primary_part,self.primary_part)
                if len(self.extended_part)!=0:
                    self.main_part_list.append(self.extended_part[0])
            elif len(self.primary_part)==0 and len(self.extended_part)!=0:
                self.main_part_list=self.extended_part
            else:#blank disk
                self.primary_part=[]
                self.extended_part=[]
                self.logical_part=[]
                self.main_part_list=[]

        #put main_part_list and logical_part into disk_space_info_tab_info_tab    
            self.disk_space_info_list[0].append(self.main_part_list)
            self.disk_space_info_list[0].append(self.logical_part)
            
            # self.disk_space_info_tab[disk][0].append(self.main_part_list)    
            # self.disk_space_info_tab[disk][0].append(self.logical_part)


        #get main_geom_list and logical_geom_list     
            if len(self.main_part_list)==0:#blank list
                self.main_geom_list=[]
            else:
                for part in self.main_part_list:
                    self.main_geom_list.append(part.geometry)
                self.main_geom_list.sort(cmp=lambda x,y:cmp(x.start,y.start))

            if len(self.logical_part)==0:#no logical part    
                self.logical_geom_list=[]
            else:
                for part in self.logical_part:
                    self.logical_geom_list.append(part.geometry)
                self.logical_geom_list.sort(cmp=lambda x,y:cmp(x.start,y.start))    
    
        #put main_geom_list and logical_geom_list into disk_space_info_tab        
            self.disk_space_info_list[1].append(self.main_geom_list)
            self.disk_space_info_list[1].append(self.logical_geom_list)
            # self.disk_space_info_tab[disk][1].append(self.main_geom_list)
            # self.disk_space_info_tab[disk][1].append(self.logical_geom_list)

        #get main_geom_gap_list and logical_geom_gap_list    
            #get main_geom_gap_list
            if len(self.main_geom_list)==0 or len(self.main_part_list)==0:
                start=disk.getFreeSpaceRegions()[0].start+4
                end=disk.getFreeSpaceRegions()[-1].end-4
                length=end-start+1
                if length > 0:
                    self.main_geom_gap_list.append(parted.geometry.Geometry(disk.device,start,length,end,None))
                else:
                    self.main_geom_gap_list=[]
            else:
                start=disk.getFreeSpaceRegions()[0].start+4
                end=self.main_geom_list[0].start-4
                length=end-start+1
                if length > 0:
                    self.main_geom_gap_list.append(parted.geometry.Geometry(disk.device,start,length,end,None))
                else:
                    # print "start of disk have geometry overlap or disk size too small"
                    self.lu.do_log_msg(self.logger,"warning","start of disk have geometry overlap or disk size too small")
                for i in range(len(self.main_geom_list)-1):
                    start=self.main_geom_list[i].end+4
                    end=self.main_geom_list[i+1].start-4
                    length=end-start+1
                    if length > 0:
                        self.main_geom_gap_list.append(parted.geometry.Geometry(disk.device,start,length,end,None))
                    else:
                        # print "the size between two partition is too small"
                        self.logger.warning("the size between two partition is too small")
                        # self.lu.do_log_msg(self.logger,"warning","the size between two partition is too small")
                    i=i+1    
        
                start=self.main_geom_list[-1].end+4    
                end=disk.getFreeSpaceRegions()[-1].end-4 
                length=end-start+1
                if length > 0:
                    self.main_geom_gap_list.append(parted.geometry.Geometry(disk.device,start,length,end,None))
                else:
                    # print "end of disk have geometry overlap or disk size too small"
                    self.logger.warning("end of disk have geometry overlap or disk size too small")
                    # self.lu.do_log_msg(self.logger,"warning","end of disk have geometry overlap or disk size too small")
            #get logical_geom_gap_list        
            if len(self.logical_geom_list)==0 and len(self.extended_part)!=0:
                start=self.extend_part.geometry.start+4
                end=self.extend_part.geometry.end-4
                length=end-start+1
                if length > 0:
                    self.logical_geom_gap_list.append(parted.geometry.Geometry(disk.device,start,length,end,None))
                else:
                    self.logical_geom_gap_list=[]
                    # print "the hole extend_part size is too small"
                    self.lu.do_log_msg(self.logger,"error","the hole extend_part size is too small")
            elif len(self.extended_part)!=0:
                start=self.extend_part.geometry.start+4
                end=self.logical_geom_list[0].start-4
                length=end-start
                if length > 0:
                    self.logical_geom_gap_list.append(parted.geometry.Geometry(disk.device,start,length,end,None))
                else:
                    # print "the space between start of extend_part and the first logical is too small"
                    self.lu.do_log_msg(self.logger,"warning","the space between start of extended_part and the first logical is too small")
                for i in range(len(self.logical_geom_list)-1):
                    start=self.logical_geom_list[i].end+4
                    end=self.logical_geom_list[i+1].start-4
                    length=end-start+1
                    if length > 0:
                        self.logical_geom_gap=parted.geometry.Geometry(disk.device,start,length,end,None)
                        self.logical_geom_gap_list.append(self.logical_geom_gap)
                    else:
                        # print "the size between two logical partition is too small"
                        self.lu.do_log_msg(self.logger,"warning","the size between two logical partition is too small")
                    i=i+1    
        
                start=self.logical_geom_list[-1].end+4
                end=self.extend_part.geometry.end-4
                length=end-start
                if length > 0:
                    self.logical_geom_gap_list.append(parted.geometry.Geometry(disk.device,start,length,end,None))
                else:
                    # print "end of extend_part have geometry overlap or disk is too small to satisfy the minlength"
                    self.lu.do_log_msg(self.logger,"warning","end of extended_part have geometry overlap")
            else:
                # print "the disk "+disk.device.path+" has no extend_part,no need to add logical_geom_gap_list"
                self.lu.do_log_msg(self.logger,"warning","no extend_part,no need to add logical_geom_gap_list")
                self.logical_geom_gap_list=[]

            #put main_geom_gap_list and logical_geom_gap_list into self.disk_space_info_tab
            # self.disk_space_info_tab[disk][2].append(self.main_geom_gap_list)
            # self.disk_space_info_tab[disk][2].append(self.logical_geom_gap_list)
            self.disk_space_info_list[2].append(self.main_geom_gap_list)
            self.disk_space_info_list[2].append(self.logical_geom_gap_list)

            self.disk_space_info_tab[disk]=self.disk_space_info_list
            
        return self.disk_space_info_tab    


    def get_disk_total_available_space_size(self,disk):
        '''return the total available space size for user to create his primary/extended/logical partition'''
        disk_space_info_tab=self.get_disk_free_space_info()
        self.main_available_space_size=""
        self.logical_available_space_size=""
        self.total_available_space_size=()
        main_length=0
        logical_length=0
        if disk_space_info_tab.has_key(disk):
            disk_space_info_list=disk_space_info_tab[disk]
            for geom in disk_space_info_list[2][0]:#main_geom_gap_list
                main_length+=geom.length
            for geom in disk_space_info_list[2][1]:#logical_geom_gap_list
                logical_length+=geom.length
        else:
            print "cann't find disk in the disk_free_space_info"
            self.lu.do_log_msg(self.logger,"error","cann't find disk in the disk_free_space_info")
        self.main_available_space_size=main_length*disk.device.sectorSize/(1024*1024)    
        self.logical_available_space_size=logical_length*disk.device.sectorSize/(1024*1024)
        self.total_available_space_size=(self.main_available_space_size,self.logical_available_space_size)

        return self.total_available_space_size

    def get_disk_single_available_space_size(self,disk,part_type):
        '''return the max size for user to create a single partition,not used in the tree view list'''
        disk_space_info_tab=self.get_disk_free_space_info()
        import math
        self.single_available_space_size=0
        if disk_space_info_tab.has_key(disk):
            disk_space_info_list=disk_space_info_tab[disk]
            if part_type=="primary" or part_type=="extend" or part_type=="extended":
                max_geo=disk_space_info_list[2][0][0]
                for geom in disk_space_info_list[2][0]:
                    if geom.length > max_geo.length:
                        max_geo=geom
                    else:
                        continue
                self.single_available_space_size=math.floor((max_geo.length*disk.device.sectorSize)/(1024*1024))
                return self.single_available_space_size

            elif part_type=="logical":
                max_geo=disk_space_info_list[2][1][0]
                for geom in disk_space_info_list[2][1]:
                    if geom.length > max_geo.length:
                        max_geo=geom
                    else:
                        continue
                self.single_available_space_size=math.floor((max_geo.length*disk.device.sectorSize)/(1024*1024))
                return self.single_available_space_size
    
            else:
                print "invalid part_type"
                self.lu.do_log_msg(self.logger,"error","invalid part_type")
        else:
            print "cann't find disk in the disk_free_space_info"
            self.lu.do_log_msg(self.logger,"error","cann't find disk in the disk_free_space_info")

    def get_disk_free_geometry(self,disk,part_type,minlength):
        '''get free geometry to add part:specified by part_type and minlength,use disk_free_space_info'''
        disk_space_info_tab=self.get_disk_free_space_info()

        self.geometry=""
        if disk_space_info_tab.has_key(disk):
            disk_space_info_list=disk_space_info_tab[disk]
            if part_type=="primary" or part_type=="extend":
                max_geo=disk_space_info_list[2][0][0]
                for geom in disk_space_info_list[2][0]:
                    if geom.length > max_geo.length:
                        max_geo=geom
                    else:
                        continue
                self.geometry=max_geo
                if self.geometry.length >= minlength:
                    return self.geometry
                else:
                    # print "cann't get a main part satisfy the minlength"
                    self.lu.do_log_msg(self.logger,"error","cann't get a main part satisfy the minlength")
    
            elif part_type=="logical":
                max_geo=disk_space_info_list[2][1][0]
                for geom in disk_space_info_list[2][1]:
                    if geom.length > max_geo.length:
                        max_geo=geom
                    else:
                        continue
                self.geometry=max_geo
                if self.geometry.length >= minlength:
                    return self.geometry
                else:
                    # print "cann't get a logical part satisfy the minlength"
                    self.lu.do_log_msg(self.logger,"error","cann't get a logical part satisfy the minlength")
            else:
                # print "invalid part type"
                self.lu.do_log_msg(self.logger,"error","invalid part type")
        else:
            # print "get_disk_free_geometry:cann't find disk in the disk_free_space_info"
            self.lu.do_log_msg(self.logger,"critical","cann't find disk in the disk_free_space_info")

    def get_disk_logical_freepart(self,disk):
        '''attention:this freepart are logical,not in the path_disk_partitions and disk_partition_info_tab,
        used for locate geometry to create new partition'''
#to be implemented,consider to delete this,just use get_disk_free_geometry
        pass

    def edit_disk_partition(self,disk,partition,info):
        '''edit partitiion size and file system,actually edit fs and geometry'''
        self.part_info=self.get_disk_partition_info(partition)
        self.part_size=partition.getSize()
        self.part_maxava_size=partition.getMaxAvailableSize(unit="MB")


    def generate_view_partition_path(self):
        '''calc partition path display to user,and as arg to manage disk_partition_info_tab
        set/get partition path for the tree view'''
        # to be implement
        pass

#should use global part_util to keep disk/partition/device id uniquee
global_part_util=PartUtil()

    
if  __name__=="__main__":
    pu=PartUtil()
