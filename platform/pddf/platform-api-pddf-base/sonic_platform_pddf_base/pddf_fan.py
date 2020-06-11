#!/usr/bin/env python


# Sample pddf_fanutil file 
# All the supported FAN SysFS aattributes are
#- fan<idx>_present
#- fan<idx>_direction
#- fan<idx>_input
#- fan<idx>_pwm
#- fan<idx>_fault
# where idx is in the range [1-6]
#



try:
    import os.path
    import sys, traceback, time
    #sys.path.append('/usr/share/sonic/platform/sonic_platform')
    import pddfparse
    import json
    from sonic_platform_base.fan_base import FanBase
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")


class PddfFan(FanBase):
    """PDDF generic Fan class"""
    color_map = {
         "STATUS_LED_COLOR_GREEN" : "on",
         "STATUS_LED_COLOR_RED" : "faulty",
         "STATUS_LED_COLOR_OFF" : "off"
    }

    pddf_obj = {}
    plugin_data = {}

    def __init__(self, tray_idx, fan_idx=0, is_psu_fan=False, psu_index=0):
        # idx is 0-based 
        #with open(os.path.join(os.path.dirname(os.path.realpath(__file__)) + '/../../../platform/pddf/pd-plugin.json')) as pd:
        with open('/usr/share/sonic/platform/pddf/pd-plugin.json') as pd:
            self.plugin_data = json.load(pd)

        self.pddf_obj = pddfparse.PddfParse()
        self.platform = self.pddf_obj.get_platform()
        if tray_idx<0 or tray_idx>=self.platform['num_fantrays']:
            print "Invalid fantray index %d\n"%tray_idx
            return
        
        if fan_idx<0 or fan_idx>=self.platform['num_fans_pertray']:
            print "Invalid fan index (within a tray) %d\n"%fan_idx
            return

        self.fantray_index = tray_idx+1
        self.fan_index = fan_idx+1
        self.is_psu_fan = is_psu_fan
        if self.is_psu_fan:
            self.fans_psu_index = psu_index

        #self.is_rear = is_rear #TODO: Should this be included in __init__ arguments



    def get_name(self):
        """
        Retrieves the fan name
        Returns: String containing fan-name
        """
        if self.is_psu_fan:
            return "PSU{}_FAN{}".format(self.fans_psu_index, self.fan_index)
        else:
            if 'name' in self.plugin_data['FAN']:
                return self.plugin_data['FAN']['name'][str(self.fantray_index)]
            else:
                return "Fantray{}_{}".format(self.fantray_index, self.fan_index)

    def get_presence(self):
        if self.is_psu_fan:
            return True
        else:
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
            attr_name = "fan" + str(idx) + "_present"
            #sysfs_path = self.pddf_obj.get_path("FAN-CTRL", attr_name)
            output = self.pddf_obj.get_attr_name_output("FAN-CTRL", attr_name)
            if not output:
                return False

            mode = output['mode']
            presence = output['status'].rstrip()

            vmap = self.plugin_data['FAN']['present'][mode]['valmap']

            if presence in vmap:
                status = vmap[presence]
            else:
                status = False

            return status

    #def get_model(self):
        #"""
        #Retrieves the model number (or part number) of the device

        #Returns:
            #string: Model/part number of device
        #"""
        #raise NotImplementedError

    #def get_serial(self):
        #"""
        #Retrieves the serial number of the device

        #Returns:
            #string: Serial number of device
        #"""
        #raise NotImplementedError

    def get_status(self):
        speed = self.get_speed()
        status = True if (speed != 0) else False
        return status

    def get_direction(self):
        """
        Retrieves the direction of fan

        Returns:
            A string, either FAN_DIRECTION_INTAKE or FAN_DIRECTION_EXHAUST
            depending on fan direction
        """
        if self.is_psu_fan:
            attr = "psu_fan_dir"
            device = "PSU{}".format(self.fans_psu_index)
            output = self.pddf_obj.get_attr_name_output(device, "psu_fan_dir")
            if not output:
                return False

            mode = output['mode']
            val = output['status']

            val = val.rstrip()
            vmap = self.plugin_data['PSU']['psu_fan_dir'][mode]['valmap']

            if val in vmap:
                direction = vmap[val]
            else:
                direction = val

        else:
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
            attr = "fan" + str(idx) + "_direction"
            output = self.pddf_obj.get_attr_name_output("FAN-CTRL", attr)
            if not output:
                return False

            mode = output['mode']
            val = output['status']

            val = val.rstrip()
            vmap = self.plugin_data['FAN']['direction'][mode]['valmap']
            if val in vmap:
                direction = vmap[val]
            else:
                direction = val

        return direction

    def get_speed(self):
        """
        Retrieves the speed of fan as a percentage of full speed

        Returns:
            An integer, the percentage of full fan speed, in the range 0 (off)
                 to 100 (full speed)
        """
        if self.is_psu_fan:
            attr = "psu_fan{}_speed_rpm".format(self.fan_index)
            device = "PSU{}".format(self.fans_psu_index)
            output = self.pddf_obj.get_attr_name_output(device, attr)
            if not output:
                return 0

            mode = output['mode']
            output['status'] = output['status'].rstrip()
            if output['status'].isalpha():
                return 0
            else:
                speed = int(output['status'])

            max_speed = int(self.plugin_data['PSU']['PSU_FAN_MAX_SPEED'])
            speed_percentage = (speed*100)/max_speed
            return speed_percentage
        else:
            # TODO This calculation should change based on MAX FAN SPEED
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
            attr = "fan" + str(idx) + "_pwm"
            output = self.pddf_obj.get_attr_name_output("FAN-CTRL", attr)

            if not output:
                return 0
            
            mode = output['mode']
            output['status'] = output['status'].rstrip()
            if output['status'].isalpha():
                return 0
            else:
                fpwm = int(output['status'])

            pwm_to_dc = eval(self.plugin_data['FAN']['pwm_to_duty_cycle'])
            speed_percentage = int(round(pwm_to_dc(fpwm)))
            #print "Speed: %d%%\n"%(speed_percentage)

            return speed_percentage

    def get_speed_rpm(self):
        """
        Retrieves the speed of fan in RPM

        Returns:
            An integer, Speed of fan in RPM
        """
        if self.is_psu_fan:
            attr = "psu_fan{}_speed_rpm".format(self.fan_index)
            device = "PSU{}".format(self.fans_psu_index)
            output = self.pddf_obj.get_attr_name_output(device, attr)
            if not output:
                return 0
            
            mode = output['mode']
            output['status'] = output['status'].rstrip()
            if output['status'].isalpha():
                return 0
            else:
                speed = int(float(output['status']))

            rpm_speed = speed
            return rpm_speed
        else:
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
            attr = "fan" + str(idx) + "_input"
            output = self.pddf_obj.get_attr_name_output("FAN-CTRL", attr)

            if output is None:
                return 0

            mode = output['mode']
            output['status'] = output['status'].rstrip()
            if output['status'].isalpha():
                return 0
            else:
                rpm_speed = int(float(output['status']))

            return rpm_speed

    def get_target_speed(self):
        """
        Retrieves the target (expected) speed of the fan

        Returns:
            An integer, the percentage of full fan speed, in the range 0 (off)
                 to 100 (full speed)
        """
        target_speed = 0
        if self.is_psu_fan:
            # Target speed not usually supported for PSU fans
            target_speed = 0
        else:
            idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
            attr = "fan" + str(idx) + "_pwm"
            output = self.pddf_obj.get_attr_name_output("FAN-CTRL", attr)

            if not output:
                return 0
            
            mode = output['mode']
            output['status'] = output['status'].rstrip()
            if output['status'].isalpha():
                return 0
            else:
                fpwm = int(output['status'])

            pwm_to_dc = eval(self.plugin_data['FAN']['pwm_to_duty_cycle'])
            speed_percentage = int(round(pwm_to_dc(fpwm)))
            target_speed = speed_percentage

        return target_speed

    def get_speed_tolerance(self):
        """
        Retrieves the speed tolerance of the fan

        Returns:
            An integer, the percentage of variance from target speed which is
                 considered tolerable
        """
        # Fix the speed vairance to 10 percent. If it changes based on platforms, overwrite 
        # this value in derived pddf fan class
        return 10

    def set_speed(self, speed):
        """
        Sets the fan speed

        Args:
            speed: An integer, the percentage of full fan speed to set fan to,
                   in the range 0 (off) to 100 (full speed)

        Returns:
            A boolean, True if speed is set successfully, False if not
        """
        if self.is_psu_fan:
            print "Setting PSU fan speed is not allowed"
            return False
        else:
            if speed<0 or speed>100:
                print "Error: Invalid speed %d. Please provide a valid speed percentage"%speed
                return False

            if 'duty_cycle_to_pwm' not in self.plugin_data['FAN']:
                print "Setting fan speed is not allowed !"
                return False
            else:
                duty_cycle_to_pwm = eval(self.plugin_data['FAN']['duty_cycle_to_pwm'])
                pwm = int(round(duty_cycle_to_pwm(speed)))

                #print "New Speed: %d%% - PWM value to be set is %d\n"%(speed,pwm)

                status = False
                idx = (self.fantray_index-1)*self.platform['num_fans_pertray'] + self.fan_index
                attr = "fan" + str(idx) + "_pwm"
                output = self.pddf_obj.set_attr_name_output("FAN-CTRL", attr, pwm)
                if not output:
                    return False
                
                mode = output['mode']
                status = output['status']

                #print "Done changing the speed of all the fans ... Reading the speed to crossscheck\n"
                return status

    def set_status_led(self, color):
        index = str(self.fantray_index-1)
        color_state="SOLID"
        led_device_name = "FANTRAY{}".format(self.fantray_index) + "_LED"

        if (not led_device_name in self.pddf_obj.data.keys()):
                print "ERROR: " + led_device_name + " is not configured"
                return (False)

        if (not color in self.color_map.keys()):
                print "ERROR: Invalid color"
                return (False)


        if(not self.pddf_obj.is_led_device_configured(led_device_name, self.color_map[color])):
                print "ERROR :" + led_device_name + ' ' + color + " is not supported in the platform"
                return (False)

        device_name=self.pddf_obj.data[led_device_name]['dev_info']['device_name']
        self.pddf_obj.create_attr('device_name', device_name,  self.pddf_obj.get_led_path())
        self.pddf_obj.create_attr('index', index, self.pddf_obj.get_led_path())
        self.pddf_obj.create_attr('color', self.color_map[color], self.pddf_obj.get_led_cur_state_path())
        self.pddf_obj.create_attr('color_state', color_state, self.pddf_obj.get_led_cur_state_path())
        self.pddf_obj.create_attr('dev_ops', 'set_status',  self.pddf_obj.get_led_path())
        return (True)


    def get_status_led(self):
        index = str(self.fantray_index-1)
        fan_led_device = "FANTRAY{}".format(self.fantray_index) + "_LED"

        if (not fan_led_device in self.pddf_obj.data.keys()):
            status = fan_led_device + " is not configured"
            # Implement a generic status_led color scheme
            if self.get_status():
                return self.STATUS_LED_COLOR_GREEN
            else:
                return self.STATUS_LED_COLOR_OFF

        device_name=self.pddf_obj.data[fan_led_device]['dev_info']['device_name']
        self.pddf_obj.create_attr('device_name', device_name,  self.pddf_obj.get_led_path())
        self.pddf_obj.create_attr('index', index, self.pddf_obj.get_led_path())
        self.pddf_obj.create_attr('dev_ops', 'get_status',  self.pddf_obj.get_led_path())
        color=self.pddf_obj.get_led_color()
        return (color)

    def dump_sysfs(self):
        return self.pddf_obj.cli_dump_dsysfs('fan')
