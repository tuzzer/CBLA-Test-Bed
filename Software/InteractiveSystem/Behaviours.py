import InteractiveCmd
from InteractiveCmd import command_object

from copy import copy
from time import clock
from time import sleep
import math


class Hardcoded_Behaviours(InteractiveCmd.InteractiveCmd):

    def run(self):
        pass


class Test_Behaviours(InteractiveCmd.InteractiveCmd):

    def run(self):

        teensy_names = self.teensy_manager.get_teensy_name_list()

        indicator_led_period = dict()
        indicator_led_on = dict()
        for teensy_name in teensy_names:
            indicator_led_period[teensy_name] = 0
            indicator_led_on[teensy_name] = 1

        loop = 0
        num_loop = 10000
        while loop < num_loop:
            start_time = clock()

            if self.teensy_manager.get_num_teensy_thread() == 0:
                return

            for teensy_name in list(teensy_names):

                Teensy_thread = self.teensy_manager.get_teensy_thread(teensy_name)

                # check if the thread is still alive
                if Teensy_thread is not None:

                    #=== "Basic" commands"
                    cmd_obj = command_object(teensy_name, 'basic')


                    cmd_obj.add_param_change('indicator_led_on',  indicator_led_on[teensy_name])
                    cmd_obj.add_param_change('indicator_led_period', int(indicator_led_period[teensy_name])*50)

                    cmd_obj.add_param_change('reply_type_request', 1)

                    self.enter_command(cmd_obj)

            self.send_commands()

            all_input_states = self.get_input_states(teensy_names, ('all', ))
            for teensy_name, input_states in all_input_states.items():
                sample = input_states[0]
                is_new_update = input_states[1]

                print("[", teensy_name, "]")

                for j in range(4):
                    device_header = 'tentacle_%d_' % j
                    print("Tentacle %d" % j, end=" ---\t")
                    print("IR (", sample[device_header + 'ir_0_state'], ", ", sample[device_header + 'ir_1_state'], ")", end="  \t")
                    print("ACC (", sample[device_header + 'acc_x_state'], ', ', sample[device_header + 'acc_y_state'], ', ', sample[device_header + 'acc_z_state'], ")" )

                for j in range(2):
                    device_header = 'protocell_%d_' % j
                    print("Protocell %d" % j, end=" ---\t")
                    print("ALS (", sample[device_header + 'als_state'], ")")
                print('')

                # new blink period
                indicator_led_period[teensy_name] += 0.004
                indicator_led_period[teensy_name] %= 10


            #     if sample['tentacle_2_acc_x_state'] == 0:
            #         crash_count += 1
            #     else:
            #         crash_count = 0
            #
            # if crash_count > 20:
            #     break

            print("Loop Time:", clock() - start_time)
            loop += 1
           # sleep(0.5)

       # print("Crash Time: ", clock() - test_start_time)

class ProgrammUpload(InteractiveCmd.InteractiveCmd):

    def run(self):
        teensy_names = self.teensy_manager.get_teensy_name_list()

        if self.teensy_manager.get_num_teensy_thread() == 0:
            return

        for teensy_name in list(teensy_names):

            Teensy_thread = self.teensy_manager.get_teensy_thread(teensy_name)

            # check if the thread is still alive
            while Teensy_thread is not None:

                #=== programming command ===
                cmd_obj = command_object(teensy_name, 'prgm')
                cmd_obj.add_param_change('program_teensy', 1)

                self.enter_command(cmd_obj)

                self.send_commands()

                Teensy_thread = self.teensy_manager.get_teensy_thread(teensy_name)

            sleep(3)
