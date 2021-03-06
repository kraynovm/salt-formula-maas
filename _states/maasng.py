
import logging
from salt.exceptions import CommandExecutionError, SaltInvocationError

LOG = logging.getLogger(__name__)

SIZE = {
    "M": 1000000,
    "G": 1000000000,
    "T": 1000000000000,
}

RAID = {
    0: "raid-0",
    1: "raid-1",
    5: "raid-5",
    10: "raid-10",
}

def __virtual__():
    '''
    Load MaaSng module
    '''
    return 'maasng'

def disk_layout_present(hostname, layout_type, root_size=None, root_device=None, volume_group=None, volume_name=None, volume_size=None, disk={} , **kwargs):
    '''
    Ensure that the disk layout does exist

    :param name: The name of the cloud that should not exist
    '''
    ret = {'name': hostname,
           'changes': {},
           'result': True,
           'comment': 'Disk layout "{0}" updated'.format(hostname)}

    machine = __salt__['maasng.get_machine'](hostname)
    if "error" in machine:
        ret['comment'] = "State execution failed for machine {0}".format(hostname)
        ret['result'] = False
        ret['changes'] = machine
        return ret

    if machine["status_name"] != "Ready":
        ret['comment'] = 'Machine {0} is not in Ready state.'.format(hostname)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Disk layout will be updated on {0}, this action will delete current layout.'.format(hostname)
        return ret

    if layout_type == "flat":

        ret["changes"] = __salt__['maasng.update_disk_layout'](hostname, layout_type, root_size, root_device)

    elif layout_type == "lvm":

        ret["changes"] = __salt__['maasng.update_disk_layout'](hostname, layout_type, root_size, root_device, volume_group, volume_name, volume_size)

    else:
        ret["comment"] = "Not supported layout provided. Choose flat or lvm"
        ret['result'] = False

    return ret

def raid_present(hostname, name, level, devices=[], partitions=[], partition_schema={}):
    '''
    Ensure that the raid does exist

    :param name: The name of the cloud that should not exist
    '''

    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Raid {0} presented on {1}'.format(name, hostname)}

    machine = __salt__['maasng.get_machine'](hostname)
    if "error" in machine:
        ret['comment'] = "State execution failed for machine {0}".format(hostname)
        ret['result'] = False
        ret['changes'] = machine
        return ret

    if machine["status_name"] != "Ready":
        ret['comment'] = 'Machine {0} is not in Ready state.'.format(hostname)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Raid {0} will be updated on {1}'.format(name,hostname)
        return ret

    #Validate that raid exists
    ##With correct devices/partition
    #OR
    ##Create raid

    ret["changes"] = __salt__['maasng.create_raid'](hostname=hostname, name=name, level=level, disks=devices, partitions=partitions)

    #TODO partitions
    ret["changes"].update(disk_partition_present(hostname, name, partition_schema)["changes"])

    if "error" in ret["changes"]:
        ret["result"] = False

    return ret


def disk_partition_present(hostname, disk, partition_schema={}):
    '''
    Ensure that the disk has correct partititioning schema

    :param name: The name of the cloud that should not exist
    '''

    #1. Validate that disk has correct values for size and mount
        #a. validate count of partitions
        #b. validate size of partitions
    #2. If not delete all partitions on disk and recreate schema
    #3. Validate type exists
        #if should not exits
        #delete mount and unformat
    #4. Validate mount exists
    #5. if not enforce umount or mount

    ret = {'name': hostname,
           'changes': {},
           'result': True,
           'comment': 'Disk layout {0} presented'.format(disk)}

    machine = __salt__['maasng.get_machine'](hostname)
    if "error" in machine:
        ret['comment'] = "State execution failed for machine {0}".format(hostname)
        ret['result'] = False
        ret['changes'] = machine
        return ret

    if machine["status_name"] != "Ready":
        ret['comment'] = 'Machine {0} is not in Ready state.'.format(hostname)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Partition schema will be changed on {0}'.format(disk)
        return ret

    partitions = __salt__['maasng.list_partitions'](hostname, disk)

    ##Calculate actual size in bytes from provided data
    for part_name, part in partition_schema.iteritems():
        size, unit = part["size"][:-1], part["size"][-1]
        part["calc_size"] = int(size) * SIZE[unit]

    if len(partitions) == len(partition_schema):

        for part_name, part in partition_schema.iteritems():
            LOG.info('validated {0}'.format(part["calc_size"]))
            LOG.info('validated {0}'.format(int(partitions[disk+"-"+part_name.split("-")[-1]]["size"])))
            if part["calc_size"] == int(partitions[disk+"-"+part_name.split("-")[-1]]["size"]):
                LOG.info('validated')
                #TODO validate size (size from maas is not same as calculate?)
                #TODO validate mount
                #TODO validate fs type
            else:
                LOG.info('breaking')
                break
            return ret

    #DELETE and RECREATE
    LOG.info('delete')
    for partition_name, partition in partitions.iteritems():
        LOG.info(partition)
        ##TODO IF LVM create ERROR
        ret["changes"] = __salt__['maasng.delete_partition_by_id'](hostname, disk, partition["id"])

    LOG.info('recreating')
    for part_name, part in partition_schema.iteritems():
        LOG.info("partitition for creation")
        LOG.info(part)
        if "mount" not in part:
            part["mount"] = None
        if "type" not in part:
            part["type"] = None
        ret["changes"] = __salt__['maasng.create_partition'](hostname, disk, part["size"], part["type"], part["mount"])

    if "error" in ret["changes"]:
        ret["result"] = False

    return ret

def volume_group_present(hostname, name, devices=[], partitions=[]):
    '''
    Ensure that the disk layout does exist

    :param name: The name of the cloud that should not exist
    '''
    ret = {'name': hostname,
        'changes': {},
        'result': True,
        'comment': 'LVM group {0} presented on {1}'.format(name,hostname)}

    machine = __salt__['maasng.get_machine'](hostname)
    if "error" in machine:
        ret['comment'] = "State execution failed for machine {0}".format(hostname)
        ret['result'] = False
        ret['changes'] = machine
        return ret

    if machine["status_name"] != "Ready":
        ret['comment'] = 'Machine {0} is not in Ready state.'.format(hostname)
        return ret

    #TODO validation if exists
    vgs = __salt__['maasng.list_volume_groups'](hostname)

    if name in vgs:
        #TODO validation for devices and partitions
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'LVM group {0} will be updated on {1}'.format(name,hostname)
        return ret

    ret["changes"] = __salt__['maasng.create_volume_group'](hostname, name, devices, partitions)

    if "error" in ret["changes"]:
        ret["result"] = False

    return ret

def volume_present(hostname, name, volume_group_name, size, type=None, mount=None):
    '''
    Ensure that the disk layout does exist

    :param name: The name of the cloud that should not exist
    '''

    ret = {'name': hostname,
           'changes': {},
           'result': True,
           'comment': 'LVM group {0} presented on {1}'.format(name,hostname)}

    machine = __salt__['maasng.get_machine'](hostname)
    if "error" in machine:
        ret['comment'] = "State execution failed for machine {0}".format(hostname)
        ret['result'] = False
        ret['changes'] = machine
        return ret

    if machine["status_name"] != "Ready":
        ret['comment'] = 'Machine {0} is not in Ready state.'.format(hostname)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'LVM volume {0} will be updated on {1}'.format(name,hostname)

    #TODO validation if exists

    ret["changes"] = __salt__['maasng.create_volume'](hostname, name, volume_group_name, size, type, mount)

    return ret


def select_boot_disk(hostname, name):
    '''
    Select disk that will be used to boot partition

    :param name: The name of disk on machine
    :param hostname: The hostname of machine
    '''

    ret = {'name': hostname,
           'changes': {},
           'result': True,
           'comment': 'LVM group {0} presented on {1}'.format(name,hostname)}

    machine = __salt__['maasng.get_machine'](hostname)
    if "error" in machine:
        ret['comment'] = "State execution failed for machine {0}".format(hostname)
        ret['result'] = False
        ret['changes'] = machine
        return ret

    if machine["status_name"] != "Ready":
        ret['comment'] = 'Machine {0} is not in Ready state.'.format(hostname)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'LVM volume {0} will be updated on {1}'.format(name,hostname)

    #TODO disk validation if exists

    ret["changes"] = __salt__['maasng.set_boot_disk'](hostname, name)

    return ret