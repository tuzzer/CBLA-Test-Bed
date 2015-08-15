import sys
# import resource
# # Increase max stack size from 8MB to 512MB
# resource.setrlimit(resource.RLIMIT_STACK, (2**29,-1))
# sys.setrecursionlimit(10**6)
import random

from interactive_system import CommunicationProtocol as CP
import interactive_system
from abstract_node import *

import cbla_generic_node as cbla_base
from cbla_isolated_node import *
from cbla_local_node import *
from cbla_spatial_node import *

from cbla_engine import cbla_robot

try:
    from custom_gui import *
except ImportError:
    import sys
    import os

    sys.path.insert(1, os.path.join(os.getcwd(), '..'))
    from custom_gui import *

create_new_log = True

if len(sys.argv) > 1:
    create_new_log = bool(sys.argv[1])


class CBLA(interactive_system.InteractiveCmd):
    log_dir = 'cbla_log'
    log_header = 'cbla_mode'

    def __init__(self, Teensy_manager, auto_start=True, mode='isolated'):

        # setting up the data collector
        log_dir_path = os.path.join(os.getcwd(), CBLA.log_dir)

        # create new entry folder if creating new log
        if create_new_log or not os.path.exists(log_dir_path):
            latest_log_dir = None
        # add a new session folder if continuing from old log
        else:
            # use the latest data log
            all_log_dir = []
            for dir in os.listdir(log_dir_path):
                dir_path = os.path.join(log_dir_path, dir)
                if os.path.isdir(dir_path):
                    all_log_dir.append(dir_path)

            if len(all_log_dir) > 0:
                latest_log_dir = max(all_log_dir, key=os.path.getmtime)
            else:
                latest_log_dir = None
        # create the data_logger
        self.data_logger = DataLogger(log_dir=CBLA.log_dir, log_header=CBLA.log_header, log_path=latest_log_dir,
                                      save_freq=60.0, sleep_time=0.20)

        # instantiate the node_list
        self.node_list = OrderedDict()

        # Condition variable indicating that all nodes are created
        self.all_nodes_created = threading.Condition()

        # parameters
        self.mode = mode
        self.num_fin = 3
        self.num_light = 3

        super(CBLA, self).__init__(Teensy_manager, auto_start=auto_start)

    # ========= the Run function for the CBLA system based on the abstract node system=====
    def run(self):

        self.messenger = interactive_system.Messenger(self, 0.000)

        for teensy_name in self.teensy_manager.get_teensy_name_list():
            # ------ set mode ------
            cmd_obj = interactive_system.command_object(teensy_name, 'basic')
            cmd_obj.add_param_change('operation_mode', CP.CBLATestBed_Triplet_FAST.MODE_CBLA2_PRESCRIPTED)
            self.enter_command(cmd_obj)

        self.send_commands()

        # initially update the Teensys with all the output parameters here
        self.update_output_params(self.teensy_manager.get_teensy_name_list())

        # start the messenger
        self.messenger.start()

        teensy_in_use = tuple(self.teensy_manager.get_teensy_name_list())

        # instantiate all the basic components
        for teensy in teensy_in_use:

            # check if the teensy exists
            if teensy not in self.teensy_manager.get_teensy_name_list():
                print('%s does not exist!' % teensy)
                continue

            # ==== creating components related to the Light =====
            light_components = OrderedDict()
            for j in range(self.num_light):
                light_components.update(self.build_light_components(teensy_name=teensy, light_id=j))
            self.node_list.update(light_components)

            # ===== creating components for related to the Fins ====
            fin_components = OrderedDict()
            for j in range(self.num_fin):
                fin_components.update(self.build_fin_components(teensy_name=teensy, fin_id=j))
            self.node_list.update(fin_components)

        # ===== creating the CBLA Nodes ====

        # creating the isolated nodes
        cbla_nodes = self.build_isolated_nodes(teensy_names=teensy_in_use, components=self.node_list)

        # linking the nodes
        if self.mode == 'spatial_local':
            self.link_spatial_locally(cbla_nodes)
        elif self.mode == 'spatial_global':
            self.link_spatially(cbla_nodes)
        elif self.mode == 'random':
            self.link_randomly(cbla_nodes)
        elif self.mode == 'functional':
            self.link_functionally(cbla_nodes)

        # instantiate the node after the linking process
        for cbla_node in cbla_nodes.values():
            cbla_node.instantiate()

        # add cbla nodes in to the node_list
        self.node_list.update(cbla_nodes)

        # notify other threads that all nodes are created
        with self.all_nodes_created:
            self.all_nodes_created.notify_all()

        # start running nodes
        self.start_nodes()

        # wait for the nodes to destroy
        for node in self.node_list.values():
            node.join()

        return 0

    def build_fin_components(self, teensy_name, fin_id):

        fin_comps = OrderedDict()

        # 2 ir sensors each
        ir_s = Input_Node(self.messenger, teensy_name, node_name='f%d.ir-s' % fin_id,
                          input='fin_%d_ir_0_state' % fin_id)
        ir_f = Input_Node(self.messenger, teensy_name, node_name='f%d.ir-f' % fin_id,
                          input='fin_%d_ir_1_state' % fin_id)

        # 1 3-axis acceleromter each
        acc = Input_Node(self.messenger, teensy_name, node_name='f%d.acc' % fin_id,
                         x='fin_%d_acc_x_state' % fin_id,
                         y='fin_%d_acc_y_state' % fin_id,
                         z='fin_%d_acc_z_state' % fin_id)

        # 2 SMA wires each
        sma_l = Output_Node(self.messenger, teensy_name, node_name='f%d.sma-l' % fin_id,
                            output='fin_%d_sma_0_level' % fin_id)
        sma_r = Output_Node(self.messenger, teensy_name, node_name='f%d.sma-r' % fin_id,
                            output='fin_%d_sma_1_level' % fin_id)

        # 2 reflex each
        reflex_l = Output_Node(self.messenger, teensy_name, node_name='f%d.rfx-l' % fin_id,
                               output='fin_%d_reflex_0_level' % fin_id)
        reflex_m = Output_Node(self.messenger, teensy_name, node_name='f%d.rfx-m' % fin_id,
                               output='fin_%d_reflex_1_level' % fin_id)

        fin_comps[ir_s.node_name] = ir_s
        fin_comps[ir_f.node_name] = ir_f
        fin_comps[acc.node_name] = acc
        fin_comps[sma_l.node_name] = sma_l
        fin_comps[sma_r.node_name] = sma_r
        fin_comps[reflex_l.node_name] = reflex_l
        fin_comps[reflex_m.node_name] = reflex_m

        # 2 reflex driver
        reflex_l_driver_ref_temp = Var(0)
        reflex_l_driver = LED_Driver(self.messenger, node_name="%s.f%d.rfx_driver-l" % (teensy_name, fin_id),
                                     led_ref=reflex_l_driver_ref_temp,
                                     led_out=reflex_l.in_var['output'], step_period=0.0005)
        fin_comps[reflex_l_driver.node_name] = reflex_l_driver
        reflex_m_driver_ref_temp = Var(0)
        reflex_m_driver = LED_Driver(self.messenger, node_name="%s.f%d.rfx_driver-m" % (teensy_name, fin_id),
                                     led_ref=reflex_m_driver_ref_temp,
                                     led_out=reflex_m.in_var['output'], step_period=0.0005)
        fin_comps[reflex_m_driver.node_name] = reflex_m_driver

        # 2 half-fin modules
        sma_temp_l = Var(0)
        half_fin_l = Half_Fin(self.messenger, node_name='%s.f%d.hf-l' % (teensy_name, fin_id),
                              sma=sma_l.in_var['output'], temp_ref=sma_temp_l)
        sma_temp_r = Var(0)
        half_fin_r = Half_Fin(self.messenger, node_name='%s.f%d.hf-r' % (teensy_name, fin_id),
                              sma=sma_r.in_var['output'], temp_ref=sma_temp_r)

        fin_comps[half_fin_l.node_name] = half_fin_l
        fin_comps[half_fin_r.node_name] = half_fin_r

        return fin_comps

    def build_light_components(self, teensy_name, light_id):

        light_comps = OrderedDict()

        # 1 LED per protocell
        led = Output_Node(self.messenger, teensy_name=teensy_name, node_name='l%d.led' % light_id,
                          output='light_%d_led_level' % light_id)

        light_comps[led.node_name] = led

        # 1 ambient light sensor per protocell
        als = Input_Node(self.messenger, teensy_name=teensy_name, node_name='l%d.als' % light_id,
                         input='light_%d_als_state' % light_id)

        light_comps[als.node_name] = als

        # 1 LED driver
        led_ref_temp = Var(0)
        led_driver = LED_Driver(self.messenger, node_name="%s.l%d.led_driver" % (teensy_name, light_id),
                                led_ref=led_ref_temp,
                                led_out=led.in_var['output'], step_period=0.001)
        light_comps[led_driver.node_name] = led_driver
        return light_comps

    def build_isolated_nodes(self, teensy_names, components):

        cbla_nodes = OrderedDict()

        for teensy_name in teensy_names:
            # ===== constructing the Light Node =====
            # Light node is composed of an ambient light sensors and a LED
            for j in range(self.num_light):
                in_vars = OrderedDict()
                in_vars['als'] = components['%s.l%d.als' % (teensy_name, j)].out_var['input']

                out_vars = OrderedDict()
                out_vars['led'] = components['%s.l%d.led_driver' % (teensy_name, j)].in_var['led_ref']
                light_node = Isolated_Light_Node(RobotClass=cbla_robot.Robot_Light,
                                              messenger=self.messenger, data_logger=self.data_logger,
                                              cluster_name=teensy_name, node_type='light', node_id=j,
                                              in_vars=in_vars, out_vars=out_vars,
                                              s_keys=('als', ),
                                              s_ranges=((0, 4095), ),
                                              s_names=('ambient light sensor', ),
                                              m_keys=('led',), m_ranges=((0, 50),),
                                              m_names=('High-power LED',),
                                              )

                cbla_nodes[light_node.node_name] = light_node

            # ===== constructing the Half-Fin Nodes =====
            # Half-Fin Node is composed of an accelerometer, the Fin IR, and the SMA
            for j in range(self.num_fin):
                # ===== constructing the shared part of the Half-Fin Nodes ====
                in_vars = OrderedDict()
                in_vars['ir-f'] = components['%s.f%d.ir-f' % (teensy_name, j)].out_var['input']
                in_vars['acc-x'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['x']
                in_vars['acc-y'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['y']
                in_vars['acc-z'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['z']

                # ===== constructing the left Half-Fin Nodes ====
                out_vars_left = OrderedDict()
                out_vars_left['hf-l'] = components['%s.f%d.hf-l' % (teensy_name, j)].in_var['temp_ref']

                half_fin_left = Isolated_HalfFin_Node(RobotClass=cbla_robot.Robot_HalfFin,
                                                   messenger=self.messenger, data_logger=self.data_logger,
                                                   cluster_name=teensy_name, node_type='halfFin', node_id=j,
                                                   node_version='l',
                                                   in_vars=in_vars, out_vars=out_vars_left,
                                                   s_keys=('ir-f', 'acc-x', 'acc-y'),  # 'acc-z'),
                                                   s_ranges=((0, 4095),  (-255, 255), (-255, 255),), # (-255, 255)),
                                                   s_names=('fin IR sensor', 'accelerometer (x)', 'accelerometer (y)'), # 'accelerometer (z)',),
                                                   m_keys=('hf-l',), m_ranges=((130, 300),),
                                                   m_names=('Half Fin Input',)
                                                   )

                cbla_nodes[half_fin_left.node_name] = half_fin_left

                # ===== constructing the right Half-Fin Nodes ====
                out_vars_right = OrderedDict()
                out_vars_right['hf-r'] = components['%s.f%d.hf-r' % (teensy_name, j)].in_var['temp_ref']

                half_fin_right = Isolated_HalfFin_Node(RobotClass=cbla_robot.Robot_HalfFin,
                                                    messenger=self.messenger, data_logger=self.data_logger,
                                                    cluster_name=teensy_name, node_type='halfFin', node_id=j,
                                                    node_version='r',
                                                    in_vars=in_vars, out_vars=out_vars_right,
                                                    s_keys=('ir-f', 'acc-x', 'acc-y'),  # 'acc-z'),
                                                    s_ranges=((0, 4095),(-255, 255), (-255, 255)), # (-255, 255)),
                                                    s_names=('fin IR sensor', 'accelerometer (x)', 'accelerometer (y)'),  # 'accelerometer (z)',),
                                                    m_keys=('hf-r',), m_ranges=((130, 300),),
                                                    m_names=('half-fin input',)
                                                    )

                cbla_nodes[half_fin_right.node_name] = half_fin_right

            # ===== constructing the Reflex Nodes =====
            # A reflex node is composed of a scout IR and the reflex actuator
            for j in range(self.num_fin):
                # ===== constructing the shared part of the Reflex Nodes ====
                in_vars = OrderedDict()
                in_vars['ir-s'] = components['%s.f%d.ir-s' % (teensy_name, j)].out_var['input']

                # ===== constructing the Reflex Motor Node ====
                out_vars_motor = OrderedDict()
                out_vars_motor['rfx-m'] = components['%s.f%d.rfx_driver-m' % (teensy_name, j)].in_var['led_ref']
                reflex_motor = Isolated_Reflex_Node(RobotClass=cbla_robot.Robot_Reflex,
                                                 messenger=self.messenger, data_logger=self.data_logger,
                                                 cluster_name=teensy_name, node_type='reflex', node_id=j,
                                                 node_version='m',
                                                 in_vars=in_vars, out_vars=out_vars_motor,
                                                 s_keys=('ir-s', ),
                                                 s_ranges=((0, 4095), ),
                                                 s_names=('scout IR sensor', ),
                                                 m_keys=('rfx-m',), m_ranges=((0, 100),),
                                                 m_names=('reflex motor',)
                                                 )

                cbla_nodes[reflex_motor.node_name] = reflex_motor

                # ===== constructing the Reflex LED Node ====
                out_vars_led = OrderedDict()
                out_vars_led['rfx-l'] = components['%s.f%d.rfx_driver-l' % (teensy_name, j)].in_var['led_ref']
                reflex_led = Isolated_Reflex_Node(RobotClass=cbla_robot.Robot_Reflex,
                                               messenger=self.messenger, data_logger=self.data_logger,
                                               cluster_name=teensy_name, node_type='reflex', node_id=j,
                                               node_version='l',
                                               in_vars=in_vars, out_vars=out_vars_led,
                                               s_keys=('ir-s', ),
                                               s_ranges=((0, 4095), ),
                                               s_names=('scout IR sensor', ),
                                               m_keys=('rfx-l',), m_ranges=((0, 255),), m_names=('reflex led',),
                                               )

                cbla_nodes[reflex_led.node_name] = reflex_led

        return cbla_nodes

    def link_spatial_locally(self, cbla_nodes, cluster_suffix='c'):

        for node_key, cbla_node in cbla_nodes.items():
            if not isinstance(cbla_node, CBLA_Generic_Node):
                continue

            if isinstance(cbla_node, (Isolated_Light_Node, Isolated_HalfFin_Node, Isolated_Reflex_Node)):
                # find the identity of this node
                identity = node_key.split('.')
                cluster_name = identity[0]
                node_type = identity[1].split('-')
                node_id =  int(node_type[0].split('_')[-1])
                if len(node_type) > 1:
                    node_version = node_type[-1]
                else:
                    node_version = None

                # Linking for the Light node
                if isinstance(cbla_node, Isolated_Light_Node):

                    # define the vars to be added
                    linked_vars = OrderedDict()
                    linked_vars['rfx-m'] = cbla_nodes['%s.cbla_reflex_%d-m' % (cluster_name, node_id)].out_var['rfx-m']
                    linked_vars['rfx-l'] = cbla_nodes['%s.cbla_reflex_%d-l' % (cluster_name, node_id)].out_var['rfx-l']

                    for linked_var_name, linked_var in linked_vars.items():
                        if linked_var_name == 'rfx-m':
                            var_name = 'reflex motor'
                        elif linked_var_name == 'rfx-l':
                            var_name = 'reflex light'
                        else:
                            var_name = 'reflex actuator'

                        cbla_node.add_in_var(var=linked_var, var_key=linked_var_name,
                                             var_range=(0, 255), var_name=var_name,
                                             )
                # Linking for the Half-Fin Node
                elif isinstance(cbla_node, Isolated_HalfFin_Node):

                    if node_version == 'l':
                        linked_var_id = node_id
                        linked_var_version = 'l'
                    elif node_version == 'r':
                        linked_var_id = (node_id + 1) % self.num_fin
                        linked_var_version = 'm'
                    else:
                        raise ValueError('Half-Fin nodes must have either "l" or "r" version!')

                    # define the vars to be added
                    linked_vars = OrderedDict()
                    linked_node_key = 'rfx-%s' % linked_var_version
                    linked_node_name ='%s.cbla_reflex_%d-%s' % (cluster_name, linked_var_id, linked_var_version)
                    linked_vars[linked_node_key] = cbla_nodes[linked_node_name].out_var[linked_node_key]

                    for linked_var_name, linked_var in linked_vars.items():
                        if linked_var_name == 'rfx-m':
                            var_name = 'reflex motor'
                        elif linked_var_name == 'rfx-l':
                            var_name = 'reflex light'
                        else:
                            var_name = 'reflex actuator'

                        cbla_node.add_in_var(var=linked_var, var_key=linked_var_name,
                                             var_range=(0, 255), var_name=var_name,
                                             )

    def link_spatially(self, cbla_nodes):
        pass

    def link_randomly(self, cbla_nodes):
        pass

    def link_functionally(self, cbla_nodes):
        pass

    def build_local_nodes(self, teensy_name, components):

        cbla_nodes = OrderedDict()

        # ===== constructing the Light Node =====
        for j in range(self.num_light):
            in_vars = OrderedDict()
            in_vars['als'] = components['%s.l%d.als' % (teensy_name, j)].out_var['input']
            in_vars['sma-l'] = components['%s.f%d.sma-l' % (teensy_name, j)].in_var['output']
            in_vars['sma-r'] = components['%s.f%d.sma-r' % (teensy_name, j)].in_var['output']
            # in_vars['ir-f'] = components['%s.f%d.ir-f' % (teensy_name, j)].out_var['input']

            out_vars = OrderedDict()
            # out_vars['led'] = components['%s.l%d.led' % (teensy_name, j)].in_var['output']
            out_vars['led'] = components['%s.l%d.led_driver' % (teensy_name, j)].in_var['led_ref']
            light_node = Local_Light_Node(RobotClass=cbla_robot.Robot_Light,
                                          messenger=self.messenger, data_logger=self.data_logger,
                                          cluster_name=teensy_name, node_type='light', node_id=j,
                                          in_vars=in_vars, out_vars=out_vars,
                                          s_keys=('als', 'sma-l', 'sma-r'),
                                          s_ranges=((0, 4095), (0, 255), (0, 255)),
                                          s_names=('ambient light sensor', 'left sma', 'right sma'),
                                          m_keys=('led',), m_ranges=((0, 50),),
                                          m_names=('High-power LED',),
                                          )

            cbla_nodes[light_node.node_name] = light_node

        # ===== constructing the Half-Fin Nodes =====
        for j in range(self.num_fin):
            # ===== constructing the shared part of the Half-Fin Nodes ====
            in_vars = OrderedDict()
            in_vars['ir-f'] = components['%s.f%d.ir-f' % (teensy_name, j)].out_var['input']
            in_vars['acc-x'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['x']
            in_vars['acc-y'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['y']
            in_vars['acc-z'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['z']

            # ===== constructing the left Half-Fin Nodes ====
            in_vars_left = in_vars.copy()
            in_vars_left['ir-s'] = components['%s.f%d.ir-s' % (teensy_name, j)].out_var['input']

            out_vars_left = OrderedDict()
            out_vars_left['hf-l'] = components['%s.f%d.hf-l' % (teensy_name, j)].in_var['temp_ref']

            half_fin_left = Local_HalfFin_Node(RobotClass=cbla_robot.Robot_HalfFin,
                                               messenger=self.messenger, data_logger=self.data_logger,
                                               cluster_name=teensy_name, node_type='halfFin', node_id=j,
                                               node_version='l',
                                               in_vars=in_vars_left, out_vars=out_vars_left,
                                               s_keys=('ir-f', 'ir-s', 'acc-x', 'acc-y'),  # , 'acc-z'),
                                               s_ranges=((0, 4095), (0, 4095), (-255, 255), (-255, 255)),
                                               # (-255, 255)),
                                               s_names=('fin IR sensor', 'scout IR sensor',
                                                        'accelerometer (x)', 'accelerometer (y)'),
                                               # 'accelerometer (z)',),
                                               m_keys=('hf-l',), m_ranges=((130, 300),),
                                               m_names=('Half Fin Input',)
                                               )

            cbla_nodes[half_fin_left.node_name] = half_fin_left

            # ===== constructing the right Half-Fin Nodes ====
            in_vars_right = in_vars.copy()
            in_vars_right['ir-s'] = components['%s.f%d.ir-s' % (teensy_name, (j + 1) % self.num_fin)].out_var['input']

            out_vars_right = OrderedDict()
            out_vars_right['hf-r'] = components['%s.f%d.hf-r' % (teensy_name, j)].in_var['temp_ref']

            half_fin_right = Local_HalfFin_Node(RobotClass=cbla_robot.Robot_HalfFin,
                                                messenger=self.messenger, data_logger=self.data_logger,
                                                cluster_name=teensy_name, node_type='halfFin', node_id=j,
                                                node_version='r',
                                                in_vars=in_vars_right, out_vars=out_vars_right,
                                                s_keys=('ir-f', 'ir-s', 'acc-x', 'acc-y'),  # 'acc-z'),
                                                s_ranges=((0, 4095), (0, 4095), (-255, 255), (-255, 255)),
                                                # (-255, 255)),
                                                s_names=('fin IR sensor', 'scout IR sensor',
                                                         'accelerometer (x)', 'accelerometer (y)'),
                                                # 'accelerometer (z)',),
                                                m_keys=('hf-r',), m_ranges=((130, 300),),
                                                m_names=('half-fin input',)
                                                )

            cbla_nodes[half_fin_right.node_name] = half_fin_right

        # ===== constructing the Reflex Nodes =====
        for j in range(self.num_fin):
            # ===== constructing the shared part of the Reflex Nodes ====
            in_vars = OrderedDict()
            in_vars['ir-s'] = components['%s.f%d.ir-s' % (teensy_name, j)].out_var['input']
            in_vars['sma-l'] = components['%s.f%d.sma-l' % (teensy_name, j)].in_var['output']
            in_vars['sma-r'] = components['%s.f%d.sma-r' % (teensy_name, j)].in_var['output']

            # ===== constructing the Reflex Motor Node ====
            out_vars_motor = OrderedDict()
            # out_vars_motor['rfx-m'] = components['%s.f%d.rfx-m' % (teensy_name, j)].in_var['output']
            out_vars_motor['rfx-m'] = components['%s.f%d.rfx_driver-m' % (teensy_name, j)].in_var['led_ref']
            reflex_motor = Local_Reflex_Node(RobotClass=cbla_robot.Robot_Reflex,
                                             messenger=self.messenger, data_logger=self.data_logger,
                                             cluster_name=teensy_name, node_type='reflex', node_id=j,
                                             node_version='m',
                                             in_vars=in_vars, out_vars=out_vars_motor,
                                             s_keys=('ir-s', 'sma-l', 'sma-r'),
                                             s_ranges=((0, 4095), (0, 255), (0, 255)),
                                             s_names=(
                                                 'scout IR sensor', 'SMA output (left)', 'SMA output (right)'),
                                             m_keys=('rfx-m',), m_ranges=((0, 100),),
                                             m_names=('reflex motor',)
                                             )

            cbla_nodes[reflex_motor.node_name] = reflex_motor

            # ===== constructing the Reflex LED Node ====
            out_vars_led = OrderedDict()
            # out_vars_led['rfx-l'] = components['%s.f%d.rfx-l' % (teensy_name, j)].in_var['output']
            out_vars_led['rfx-l'] = components['%s.f%d.rfx_driver-l' % (teensy_name, j)].in_var['led_ref']
            reflex_led = Local_Reflex_Node(RobotClass=cbla_robot.Robot_Reflex,
                                           messenger=self.messenger, data_logger=self.data_logger,
                                           cluster_name=teensy_name, node_type='reflex', node_id=j,
                                           node_version='l',
                                           in_vars=in_vars, out_vars=out_vars_led,
                                           s_keys=('ir-s', 'sma-l', 'sma-r'),
                                           s_ranges=((0, 4095), (0, 255), (0, 255)),
                                           s_names=('scout IR sensor', 'SMA output (left)', 'SMA output (right)'),
                                           m_keys=('rfx-l',), m_ranges=((0, 255),), m_names=('reflex led',),
                                           )

            cbla_nodes[reflex_led.node_name] = reflex_led

        return cbla_nodes

    def build_spatial_nodes(self, teensy_names, components):

        cbla_nodes = OrderedDict()
        neighbour_nodes = OrderedDict()

        # === spatial sum neighbourhoods====
        vh_out_var = Var(0)
        vh_in_vars = OrderedDict()
        vh_in_vars['als-1'] = components['c1.l2.als'].out_var['input']
        vh_in_vars['als-2'] = components['c2.l1.als'].out_var['input']
        vh_in_vars['als-3'] = components['c3.l0.als'].out_var['input']
        # vh_in_vars['led-1'] = components['c1.l2.led_driver'].in_var['led_ref']
        # vh_in_vars['led-2'] = components['c2.l1.led_driver'].in_var['led_ref']
        # vh_in_vars['led-3'] = components['c3.l0.led_driver'].in_var['led_ref']

        vh1 = Spatial_Sum(messenger=self.messenger,
                          node_name='vh1.sumer',
                          output = vh_out_var,
                          **vh_in_vars
                          )

        neighbour_nodes[vh1.node_name] = vh1

        vh_out_var = Var(0)
        vh_in_vars = OrderedDict()
        vh_in_vars['als-1'] = components['c2.l2.als'].out_var['input']
        vh_in_vars['als-2'] = components['c4.l0.als'].out_var['input']
        # vh_in_vars['led-1'] = components['c2.l2.led_driver'].in_var['led_ref']
        # vh_in_vars['led-2'] = components['c4.l0.led_driver'].in_var['led_ref']

        vh2 = Spatial_Sum(messenger=self.messenger,
                          node_name='vh2.sumer',
                          output = vh_out_var,
                          **vh_in_vars
                          )

        neighbour_nodes[vh2.node_name] = vh2

        vh_out_var = Var(0)
        vh_in_vars = OrderedDict()
        vh_in_vars['als-1'] = components['c3.l2.als'].out_var['input']
        vh_in_vars['als-2'] = components['c4.l1.als'].out_var['input']
        # vh_in_vars['led-1'] = components['c3.l2.led_driver'].in_var['led_ref']
        # vh_in_vars['led-2'] = components['c4.l1.led_driver'].in_var['led_ref']

        vh3 = Spatial_Sum(messenger=self.messenger,
                          node_name='vh3.sumer',
                          output = vh_out_var,
                          **vh_in_vars
                          )
        neighbour_nodes[vh3.node_name] = vh3


        for teensy_name in teensy_names:
            # ===== constructing the Light Node =====
            for j in range(self.num_light):
                in_vars = OrderedDict()
                in_vars['als'] = components['%s.l%d.als' % (teensy_name, j)].out_var['input']
                in_vars['sma-l'] = components['%s.f%d.sma-l' % (teensy_name, j)].in_var['output']
                in_vars['sma-r'] = components['%s.f%d.sma-r' % (teensy_name, j)].in_var['output']

                # connecting points
                if (teensy_name == 'c1' and j == 2) or \
                    (teensy_name == 'c2' and j == 1) or \
                    (teensy_name == 'c3' and j == 0):
                    in_vars['vh1'] = vh1.out_var['output']
                elif (teensy_name == 'c2' and j == 2) or \
                     (teensy_name == 'c4' and j == 0):
                    in_vars['vh2'] = vh2.out_var['output']
                elif (teensy_name == 'c3' and j == 2) or \
                     (teensy_name == 'c4' and j == 1):
                    in_vars['vh3'] = vh3.out_var['output']

                out_vars = OrderedDict()
                # out_vars['led'] = components['%s.l%d.led' % (teensy_name, j)].in_var['output']
                out_vars['led'] = components['%s.l%d.led_driver' % (teensy_name, j)].in_var['led_ref']
                light_node = Local_Light_Node(RobotClass=cbla_robot.Robot_Light,
                                              messenger=self.messenger, data_logger=self.data_logger,
                                              cluster_name=teensy_name, node_type='light', node_id=j,
                                              in_vars=in_vars, out_vars=out_vars,
                                              s_keys=tuple(in_vars.keys()),
                                              s_ranges=((0, 4095), (0, 255), (0, 255), (0, 2000)),
                                              s_names=('ambient light sensor', 'left sma', 'right sma',
                                                       'high-intensity neighbourhood'),
                                              m_keys=tuple(out_vars.keys()), m_ranges=((0, 50),),
                                              m_names=('High-power LED',),
                                              )

                cbla_nodes[light_node.node_name] = light_node

            # ===== constructing the Half-Fin Nodes =====
            for j in range(self.num_fin):
                # ===== constructing the shared part of the Half-Fin Nodes ====
                in_vars = OrderedDict()
                in_vars['ir-f'] = components['%s.f%d.ir-f' % (teensy_name, j)].out_var['input']
                in_vars['acc-x'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['x']
                in_vars['acc-y'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['y']
                in_vars['acc-z'] = components['%s.f%d.acc' % (teensy_name, j)].out_var['z']

                # ===== constructing the left Half-Fin Nodes ====
                in_vars_left = in_vars.copy()
                in_vars_left['ir-s'] = components['%s.f%d.ir-s' % (teensy_name, j)].out_var['input']

                out_vars_left = OrderedDict()
                out_vars_left['hf-l'] = components['%s.f%d.hf-l' % (teensy_name, j)].in_var['temp_ref']

                half_fin_left = Local_HalfFin_Node(RobotClass=cbla_robot.Robot_HalfFin,
                                                   messenger=self.messenger, data_logger=self.data_logger,
                                                   cluster_name=teensy_name, node_type='halfFin', node_id=j,
                                                   node_version='l',
                                                   in_vars=in_vars_left, out_vars=out_vars_left,
                                                   s_keys=('ir-f', 'ir-s', 'acc-x', 'acc-y'),  # , 'acc-z'),
                                                   s_ranges=((0, 4095), (0, 4095), (-255, 255), (-255, 255)),
                                                   # (-255, 255)),
                                                   s_names=('fin IR sensor', 'scout IR sensor',
                                                            'accelerometer (x)', 'accelerometer (y)'),
                                                   # 'accelerometer (z)',),
                                                   m_keys=('hf-l',), m_ranges=((130, 300),),
                                                   m_names=('Half Fin Input',)
                                                   )

                cbla_nodes[half_fin_left.node_name] = half_fin_left

                # ===== constructing the right Half-Fin Nodes ====
                in_vars_right = in_vars.copy()
                in_vars_right['ir-s'] = components['%s.f%d.ir-s' % (teensy_name, (j + 1) % self.num_fin)].out_var['input']

                out_vars_right = OrderedDict()
                out_vars_right['hf-r'] = components['%s.f%d.hf-r' % (teensy_name, j)].in_var['temp_ref']

                half_fin_right = Local_HalfFin_Node(RobotClass=cbla_robot.Robot_HalfFin,
                                                    messenger=self.messenger, data_logger=self.data_logger,
                                                    cluster_name=teensy_name, node_type='halfFin', node_id=j,
                                                    node_version='r',
                                                    in_vars=in_vars_right, out_vars=out_vars_right,
                                                    s_keys=('ir-f', 'ir-s', 'acc-x', 'acc-y'),  # 'acc-z'),
                                                    s_ranges=((0, 4095), (0, 4095), (-255, 255), (-255, 255)),
                                                    # (-255, 255)),
                                                    s_names=('fin IR sensor', 'scout IR sensor',
                                                             'accelerometer (x)', 'accelerometer (y)'),
                                                    # 'accelerometer (z)',),
                                                    m_keys=('hf-r',), m_ranges=((130, 300),),
                                                    m_names=('half-fin input',)
                                                    )

                cbla_nodes[half_fin_right.node_name] = half_fin_right

            # ===== constructing the Reflex Nodes =====
            for j in range(self.num_fin):
                # ===== constructing the shared part of the Reflex Nodes ====
                in_vars = OrderedDict()
                in_vars['ir-s'] = components['%s.f%d.ir-s' % (teensy_name, j)].out_var['input']
                in_vars['sma-l'] = components['%s.f%d.sma-l' % (teensy_name, j)].in_var['output']
                in_vars['sma-r'] = components['%s.f%d.sma-r' % (teensy_name, j)].in_var['output']

                # ===== constructing the Reflex Motor Node ====
                out_vars_motor = OrderedDict()
                # out_vars_motor['rfx-m'] = components['%s.f%d.rfx-m' % (teensy_name, j)].in_var['output']
                out_vars_motor['rfx-m'] = components['%s.f%d.rfx_driver-m' % (teensy_name, j)].in_var['led_ref']
                reflex_motor = Local_Reflex_Node(RobotClass=cbla_robot.Robot_Reflex,
                                                 messenger=self.messenger, data_logger=self.data_logger,
                                                 cluster_name=teensy_name, node_type='reflex', node_id=j,
                                                 node_version='m',
                                                 in_vars=in_vars, out_vars=out_vars_motor,
                                                 s_keys=('ir-s', 'sma-l', 'sma-r'),
                                                 s_ranges=((0, 4095), (0, 255), (0, 255)),
                                                 s_names=(
                                                     'scout IR sensor', 'SMA output (left)', 'SMA output (right)'),
                                                 m_keys=('rfx-m',), m_ranges=((0, 100),),
                                                 m_names=('reflex motor',)
                                                 )

                cbla_nodes[reflex_motor.node_name] = reflex_motor

                # ===== constructing the Reflex LED Node ====
                out_vars_led = OrderedDict()
                # out_vars_led['rfx-l'] = components['%s.f%d.rfx-l' % (teensy_name, j)].in_var['output']
                out_vars_led['rfx-l'] = components['%s.f%d.rfx_driver-l' % (teensy_name, j)].in_var['led_ref']
                reflex_led = Local_Reflex_Node(RobotClass=cbla_robot.Robot_Reflex,
                                               messenger=self.messenger, data_logger=self.data_logger,
                                               cluster_name=teensy_name, node_type='reflex', node_id=j,
                                               node_version='l',
                                               in_vars=in_vars, out_vars=out_vars_led,
                                               s_keys=('ir-s', 'sma-l', 'sma-r'),
                                               s_ranges=((0, 4095), (0, 255), (0, 255)),
                                               s_names=('scout IR sensor', 'SMA output (left)', 'SMA output (right)'),
                                               m_keys=('rfx-l',), m_ranges=((0, 255),), m_names=('reflex led',),
                                               # robot_config=sample_size
                                               )

                cbla_nodes[reflex_led.node_name] = reflex_led

        return cbla_nodes, neighbour_nodes

    def build_random_nodes(self, teensy_names, components, inputs_per_node=3):

        cbla_nodes = OrderedDict()

        # ===== specifying variables that are being used ====
        cbla_s_vars = []
        cbla_m_vars = []
        for teensy_name in teensy_names:
            for j in range(self.num_light):
                cbla_s_vars.append(('%s.l%d.als' % (teensy_name, j),
                                    components['%s.l%d.als' % (teensy_name, j)].out_var['input'],
                                    (0, 4095), 'Ambient Light Sensor'))
                cbla_m_vars.append(('%s.l%d.led_driver' % (teensy_name, j),
                                    components['%s.l%d.led_driver' % (teensy_name, j)].in_var['led_ref'],
                                    (0, 50), 'High-Power LED'))
            for j in range(self.num_fin):
                cbla_s_vars.append(('%s.f%d.ir-f' % (teensy_name, j),
                                    components['%s.f%d.ir-f' % (teensy_name, j)].out_var['input'],
                                    (0, 4095), 'fin IR Sensor'))
                cbla_s_vars.append(('%s.f%d.ir-s' % (teensy_name, j),
                                    components['%s.f%d.ir-s' % (teensy_name, j)].out_var['input'],
                                    (0, 4095), 'scout IR Sensor'))
                cbla_s_vars.append(('%s.f%d.acc-x' % (teensy_name, j),
                                    components['%s.f%d.acc' % (teensy_name, j)].out_var['x'],
                                    (-255, 255), 'SMA (x-axis)'))
                cbla_s_vars.append(('%s.f%d.acc-y' % (teensy_name, j),
                                    components['%s.f%d.acc' % (teensy_name, j)].out_var['y'],
                                    (-255, 255), 'SMA (y-axis)'))
                cbla_s_vars.append(('%s.f%d.acc-z' % (teensy_name, j),
                                    components['%s.f%d.acc' % (teensy_name, j)].out_var['z'],
                                    (-255, 255), 'SMA (z-axis)'))

                cbla_m_vars.append(('%s.f%d.rfx_driver-l' % (teensy_name, j),
                                    components['%s.f%d.rfx_driver-l' % (teensy_name, j)].in_var['led_ref'],
                                    (0, 255), 'reflex led'))
                cbla_m_vars.append(('%s.f%d.rfx_driver-m' % (teensy_name, j),
                                    components['%s.f%d.rfx_driver-m' % (teensy_name, j)].in_var['led_ref'],
                                    (0, 255), 'reflex motor'))
                cbla_m_vars.append(('%s.f%d.hf-l' % (teensy_name, j),
                                    components['%s.f%d.hf-l' % (teensy_name, j)].in_var['temp_ref'],
                                    (0, 300), 'half-input (left)'))
                cbla_m_vars.append(('%s.f%d.hf-r' % (teensy_name, j),
                                    components['%s.f%d.hf-r' % (teensy_name, j)].in_var['temp_ref'],
                                    (0, 300), 'half-input (right)'))

        cbla_in_vars = cbla_s_vars + cbla_m_vars
        num_in_vars = len(cbla_in_vars)
        node_counter = 0
        for m_key, m_var, m_range, m_name in cbla_m_vars:
            out_vars = OrderedDict()
            out_vars[m_key] = m_var
            m_keys = (m_key,)
            m_ranges = (m_range,)
            m_names = (m_name,)

            s_idx = random.sample(range(num_in_vars), inputs_per_node)
            in_vars = OrderedDict()
            s_keys = []
            s_ranges = []
            s_names = []
            for idx in s_idx:
                try:
                    s_key = cbla_in_vars[idx][0]
                    s_var = cbla_in_vars[idx][1]
                    s_range = cbla_in_vars[idx][2]
                    s_name = cbla_in_vars[idx][3]
                except IndexError:
                    raise IndexError('%s out of range' % str(cbla_in_vars[idx]))
                in_vars[s_key] = s_var
                s_keys.append(s_key)
                s_ranges.append(s_range)
                s_names.append(s_name)

            cbla_node = cbla_base.CBLA_Generic_Node(messenger=self.messenger, data_logger=self.data_logger,
                                            cluster_name=m_name, node_type='random', node_id=node_counter,
                                            in_vars=in_vars, out_vars=out_vars,
                                            s_keys=tuple(s_keys), s_ranges=tuple(s_ranges), s_names=tuple(s_names),
                                            m_keys=tuple(m_keys), m_ranges=tuple(m_ranges), m_names=tuple(m_names)
                                            )
            cbla_nodes[cbla_node.node_name] = cbla_node
            node_counter += 1

        return cbla_nodes

    def start_nodes(self):

        if not isinstance(self.node_list, dict) or \
                not isinstance(self.data_logger, DataLogger) or \
                not isinstance(self.messenger, interactive_system.Messenger):
            raise AttributeError("Nodes have not been created properly!")

        for name, node in self.node_list.items():
            node.start()
            print('%s initialized' % name)
        print('System Initialized with %d nodes' % len(self.node_list))

        # start the Data Collector
        self.data_logger.start()
        print('Data Collector initialized.')

    # loop that poll user's input from the console
    def termination_input_thread(self):

        if not isinstance(self.node_list, dict) or \
                not isinstance(self.data_logger, DataLogger):
            raise AttributeError("Nodes have not been created properly!")

        input_str = ''
        while not input_str == 'exit':
            input_str = input("\nEnter 'exit' to terminate program: \t")

            if input_str == 'save_states':
                CBLA.save_cbla_node_states(self.node_list)
                print('state_saved')

            else:
                if not input_str == 'exit':
                    print('command does not exist!')

        self.terminate()

    def terminate(self):
        # killing each of the Node
        for node in self.node_list.values():
            node.alive = False
        for node in self.node_list.values():
            node.join()
            print('%s is terminated.' % node.node_name)

        # terminating the data_collection thread
        self.data_logger.end_data_collection()
        self.data_logger.join()
        print("Data Logger is terminated.")

        # killing each of the Teensy threads
        for teensy_name in list(self.teensy_manager.get_teensy_name_list()):
            self.teensy_manager.kill_teensy_thread(teensy_name)

    @staticmethod
    def save_cbla_node_states(node_list):

        for node in node_list.values():
            if isinstance(node, cbla_base.CBLA_Base_Node):
                node.save_states()


def hmi_init(hmi: tk_gui.Master_Frame, messenger: interactive_system.Messenger, node_list: dict):
    if not isinstance(hmi, tk_gui.Master_Frame):
        raise TypeError("HMI must be Master_Frame")
    if not isinstance(node_list, dict):
        raise TypeError("node_list must be a dictionary")

    hmi.wm_title('CBLA Mode')

    status_frame = tk_gui.Messenger_Status_Frame(hmi, messenger)
    content_frame = tk_gui.Content_Frame(hmi)
    nav_frame = tk_gui.Navigation_Frame(hmi, content_frame)

    cbla_display_vars = OrderedDict()
    device_display_vars = OrderedDict()

    if len(node_list) > 0:

        for name, node in node_list.items():
            node_name = name.split('.')
            teensy_name = node_name[0]
            device_name = node_name[1]

            footer = '\nMisc.'
            if isinstance(node, Local_HalfFin_Node):
                footer = '\nHalf Fin'
                if device_name[-1] == 'l':
                    footer += ' Left'
                elif device_name[-1] == 'r':
                    footer += ' right'

            elif isinstance(node, Local_Reflex_Node):
                footer = '\nReflex'
            elif isinstance(node, Local_Light_Node):
                footer = '\nLight'
            elif isinstance(node, cbla_base.CBLA_Generic_Node):
                footer = '\nCBLA'

            page_name = teensy_name + footer

            if isinstance(node, cbla_base.CBLA_Base_Node):
                for var_name, var in node.in_var.items():

                    if page_name not in cbla_display_vars:
                        cbla_display_vars[page_name] = OrderedDict()

                    # specifying the displayable variables
                    if device_name not in cbla_display_vars[page_name]:
                        cbla_display_vars[page_name][device_name] = OrderedDict()

                    cbla_display_vars[page_name][device_name][var_name] = ({var_name: var}, 'input_node')

                for var_name, var in node.out_var.items():

                    # specifying the displayable variables
                    if device_name not in cbla_display_vars[page_name]:
                        cbla_display_vars[page_name][device_name] = OrderedDict()

                    cbla_display_vars[page_name][device_name][var_name] = ({var_name: var}, 'output_node')

            else:
                try:
                    output_name = node_name[2]
                except IndexError:
                    output_name = "variables"

                # specifying the displayable variables
                if page_name not in device_display_vars:
                    device_display_vars[page_name] = OrderedDict()

                if device_name not in device_display_vars[page_name]:
                    device_display_vars[page_name][device_name] = OrderedDict()

                if isinstance(node, Input_Node):
                    device_display_vars[page_name][device_name][output_name] = (node.out_var, 'input_node')
                elif isinstance(node, Output_Node):
                    device_display_vars[page_name][device_name][output_name] = (node.in_var, 'output_node')
                else:
                    device_display_vars[page_name][device_name][output_name + "_input"] = (node.in_var, 'input_node')
                    device_display_vars[page_name][device_name][output_name + "_output"] = (node.out_var, 'output_node')

    page_frames = OrderedDict()
    for page_name, page_vars in tuple(cbla_display_vars.items()) + tuple(device_display_vars.items()):

        teensy_display_vars = OrderedDict()
        teensy_cbla_vars = OrderedDict()

        if page_name in device_display_vars.keys():
            teensy_display_vars = device_display_vars[page_name]
        elif page_name in cbla_display_vars.keys():
            teensy_cbla_vars = cbla_display_vars[page_name]

        frame = HMI_CBLA_Mode(content_frame, page_name, (page_name, 'cbla_display_page'),
                              teensy_cbla_vars, teensy_display_vars)
        page_frames[frame.page_key] = frame

        content_frame.build_pages(page_frames)

        nav_frame.build_nav_buttons(max_per_col=15)

    print('GUI initialized.')
    hmi.start(status_frame=status_frame,
              nav_frame=nav_frame,
              content_frame=content_frame,
              start_page_key=next(iter(page_frames.keys()), ''))


if __name__ == "__main__":

    mode_config = 'spatial_local'

    if len(sys.argv) > 1:
        mode_config = str(sys.argv[1])
        mode_config = str(sys.argv[1])

    # None means all Teensy's connected will be active; otherwise should be a tuple of names
    ACTIVE_TEENSY_NAMES = None# ('c1','c4', 'c2', 'c3')
    MANDATORY_TEENSY_NAMES = ACTIVE_TEENSY_NAMES


    def main():

        # instantiate Teensy Monitor
        teensy_manager = interactive_system.TeensyManager(import_config=True)

        # find all the Teensy
        print("Number of Teensy devices found: " + str(teensy_manager.get_num_teensy_thread()))

        # kill all and only leave those specified in ACTIVE_TEENSY_NAMES
        all_teensy_names = list(teensy_manager.get_teensy_name_list())
        if isinstance(ACTIVE_TEENSY_NAMES, tuple):
            for teensy_name in all_teensy_names:
                if teensy_name not in ACTIVE_TEENSY_NAMES:
                    teensy_manager.kill_teensy_thread(teensy_name)

        # check if all the mandatory ones are still there
        if isinstance(MANDATORY_TEENSY_NAMES, tuple):
            for teensy_name in MANDATORY_TEENSY_NAMES:
                if teensy_name not in all_teensy_names:
                    raise Exception('%s is missing!!' % teensy_name)

        # find all the Teensy
        print("Number of active Teensy devices: %s\n" % str(teensy_manager.get_num_teensy_thread()))

        # interactive code
        # -- this create all the abstract nodes
        behaviours = CBLA(teensy_manager, auto_start=True, mode=mode_config)

        if not isinstance(behaviours, CBLA):
            raise TypeError("Behaviour must be CBLA type!")

        behaviours.all_nodes_created.acquire()
        behaviours.all_nodes_created.wait()
        behaviours.all_nodes_created.release()

        # initialize the gui
        hmi = tk_gui.Master_Frame()
        hmi_init(hmi, behaviours.messenger, behaviours.node_list)

        sleep(5.0)
        # input("Enter any character to terminate program...")

        behaviours.terminate()
        behaviours.join()

        for teensy_thread in teensy_manager._get_teensy_thread_list():
            teensy_thread.join()

        print("All Teensy threads terminated")


    main()
    print("\n===== Program Safely Terminated=====")
