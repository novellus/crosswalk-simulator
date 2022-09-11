import random
from collections import defaultdict
from matplotlib import pyplot as plt


# bounds for monte carlo'd values
CROSSWALK_LENGTH = (5, 30)  # meters
CROSSWALK_DURATION = (61, 200)  # seconds. lower bound set to guarantee crossability given WALKING_VELOCITY
SIDEWALK_LENGTH = (50, 150)  # meters
WALKING_VELOCITY = (0.5, 5)  # meters / second
WAIT_TIME = (0, 250)  # seconds
GRID_LENGTH = (5, 20)  # number of sidewalk blocks in each dimension of the grid


# static variables
other_direction = {'x':'y', 'y':'x'}


class traffic_light:
    def __init__(self, x_length=None, y_length=None, x_signal_duration=None, y_signal_duration=None, initial_state=None):
        self.x_length = x_length or self.random_length()
        self.y_length = y_length or self.random_length()
        self.x_signal_duration = x_signal_duration or self.random_signal_duration()
        self.y_signal_duration = y_signal_duration or self.random_signal_duration()

        initial_state = initial_state or self.random_state()
        self.state = initial_state
        self.set_initial_time_offset(initial_state = initial_state)

    def set_initial_time_offset(self, initial_state):
        # creates relative time offset based on initial_state
        # only called during initialization or unit testing
        if initial_state < 1:
            self.initial_cycle_time = self.x_signal_duration * initial_state
        else:
            self.initial_cycle_time = self.x_signal_duration + self.y_signal_duration * (initial_state - 1)

    def random_state(self):
        # state in interval [0, 2)
        #   [0, 1) => x direction is crossing
        #   [1, 2) => y direction is crossing
        return random.uniform(0, 2)

    def random_length(self):
        return random.uniform(*CROSSWALK_LENGTH)

    def random_signal_duration(self):
        return random.uniform(*CROSSWALK_DURATION)

    def set_state(self, time):
        # sets signal state based on time passed since simulation start
        mid_cycle_time = (time + self.initial_cycle_time) % (self.x_signal_duration + self.y_signal_duration)

        if mid_cycle_time < self.x_signal_duration:  # x-crossing
            self.state = mid_cycle_time / self.x_signal_duration
        else:   # y-crossing
            self.state = 1 + (mid_cycle_time - self.x_signal_duration) / self.y_signal_duration


    def time_to_cross(self, direction, velocity):
        if direction == 'x':
            return self.x_length / velocity
        else:
            return self.y_length / velocity

    def current_crossing_direction(self):
        # returns 'x' or 'y'
        if 0 <= self.state < 1:
            return 'x'
        else:
            return 'y'

    def time_until_switch_directions(self):
        # measures time until the crosswalk switches cross-direction
        if self.current_crossing_direction() == 'x':
            signal_duration = self.x_signal_duration
        else:
            signal_duration = self.y_signal_duration

        ratio_crossing_remaining = 1 - (self.state % 1)
        return ratio_crossing_remaining * signal_duration

    def time_until_switch_directions_twice(self):
        # measures time until the crosswalk switches directions twice
        if self.current_crossing_direction() == 'x':
            return self.time_until_switch_directions() + self.y_signal_duration
        else:
            return self.time_until_switch_directions() + self.x_signal_duration

    def enough_time_to_cross(self, direction, velocity):
        # returns boolean
        #   True if enough time to cross in current state
        # assumes direction matches current_crossing_direction
        return self.time_to_cross(direction, velocity) <= self.time_until_switch_directions()

    def time_until_can_cross(self, direction, velocity):
        # returns non-negative float
        # returns 0 if light is currently crossing in specified direction and there is time enough to cross at specified velocity
        # otherwise calculates time until next crossing oppurtunity is available
        #     assuming that a crossing is always possible at the beginning of a light cycle
        #     eg, that there are no lights switching faster than a pedestrian can cross
        #     this should be guaranteed by the monte carlo'd values of velocity and size

        if self.current_crossing_direction() == direction:
            if self.enough_time_to_cross(direction, velocity):
                return 0
            else:
                return self.time_until_switch_directions_twice()
        else:
            return self.time_until_switch_directions()


class sidewalk_block:
    def __init__(self, x_length=None, y_length=None):
        self.x_length = x_length or self.random_length()
        self.y_length = y_length or self.random_length()

    def random_length(self):
        return random.uniform(*SIDEWALK_LENGTH)

    def time_to_cross(self, direction, velocity):
        if direction == 'x':
            return self.x_length / velocity
        else:
            return self.y_length / velocity


class pedestrian:
    def __init__(self, velocity=None, choice_wait_time=None):
        self.velocity = velocity or self.random_velocity()
        self.choice_wait_time = choice_wait_time or self.random_choice_wait_time()

    def random_velocity(self):
        return random.uniform(*WALKING_VELOCITY)

    def random_choice_wait_time(self):
        return random.uniform(*WAIT_TIME)

    def would_choose_to_wait_for_light(self, wait_time):
        if wait_time <= self.choice_wait_time:
            return True
        else:
            return False


class city_map:
    # dynamicly creates sidewalk and light segments on demand
    #     handling size matching for grid aligned semgnets
    # tracks grid and sidewalk positions
    # mnaintains end_reached 4-state flag indicating x/y boundaries

    def __init__(self, x_length=None, y_length=None):
        self.length = {'x': x_length or self.random_length(),
                       'y': y_length or self.random_length()
                      }
        self.grid_position = {'x':1, 'y':1}  # count initial sidewalk_block
        self.sidewalk_position = 'upper_left'
        self.end_reached = False  # False, 'x', 'y', or True. 'x' and 'y' indicate maximum grid length reached in one direction

        self.sidewalk_segment = sidewalk_block()
        self.traffic_light_segments = {'upper_left': None,
                                       'lower_left': None,
                                       'upper_right': None,
                                       'lower_right': None,
                                      }

    def random_length(self):
        return random.uniform(*GRID_LENGTH)

    def new_sidewalk_block(self, direction):
        # generates new sidewalk_block in specified direction, equating one dimension of length with existing sidewalk_block
        # sets sidewalk_position on new block
        # tracks grid size restrictions
        # handles propogation of attached traffic_lights

        # create new sidewalk_block, matching one side length to adjacent current block
        args = {}
        if direction == 'x':
            args['y_length'] = self.sidewalk_segment.y_length
        else:
            args['x_length'] = self.sidewalk_segment.x_length

        self.sidewalk_segment = sidewalk_block(**args)

        # update grid position, check for maximum length
        self.grid_position[direction] += 1
        if self.grid_position[direction] >= self.length[direction]:
            if self.end_reached == False or self.end_reached == direction:
                self.end_reached = direction
            else:
                self.end_reached = True

        # update sidewalk_position
        if self.sidewalk_position == 'upper_right':
            self.sidewalk_position = 'upper_left'
        elif self.sidewalk_position == 'lower_left':
            self.sidewalk_position = 'upper_left'
        else: #  lower_right
            if direction == 'x':
                self.sidewalk_position = 'lower_left'
            else:  # y
                self.sidewalk_position = 'upper_right'

        # propogate existing light segments attached to the new sidewalk_block, clear the rest
        if direction == 'x':
            self.traffic_light_segments['upper_left'] = self.traffic_light_segments['upper_right']
            self.traffic_light_segments['lower_left'] = self.traffic_light_segments['lower_right']
            self.traffic_light_segments['upper_right'] = None

        else:  # y
            self.traffic_light_segments['upper_left'] = self.traffic_light_segments['lower_left']
            self.traffic_light_segments['upper_right'] = self.traffic_light_segments['lower_right']
            self.traffic_light_segments['lower_left'] = None

        self.traffic_light_segments['lower_right'] = None

    def get_current_traffic_light(self):
        # returns traffic light at current sidewalk_position
        # creates a new instance when needed, equating size with preexisting grid-aligned instances, if any

        # return existing light segment if it has already been created
        if self.traffic_light_segments[self.sidewalk_position] is None:

            # create new traffic_light at this sidewalk_position
            # match size to preexisting grid-aligned traffic_lights attached to this sidewalk_block
            args = {}
            if self.sidewalk_position == 'lower_right':
                if self.traffic_light_segments['lower_left'] is not None:
                    args['y_length'] = self.traffic_light_segments['lower_left'].y_length
                if self.traffic_light_segments['upper_right'] is not None:
                    args['x_length'] = self.traffic_light_segments['upper_right'].x_length

            elif self.sidewalk_position == 'upper_right':
                if self.traffic_light_segments['upper_left'] is not None:
                    args['y_length'] = self.traffic_light_segments['upper_left'].y_length
                if self.traffic_light_segments['lower_right'] is not None:
                    args['x_length'] = self.traffic_light_segments['lower_right'].x_length

            elif self.sidewalk_position == 'lower_left':
                if self.traffic_light_segments['lower_right'] is not None:
                    args['y_length'] = self.traffic_light_segments['lower_right'].y_length
                if self.traffic_light_segments['upper_left'] is not None:
                    args['x_length'] = self.traffic_light_segments['upper_left'].x_length

            elif self.sidewalk_position == 'upper_left':
                if self.traffic_light_segments['upper_right'] is not None:
                    args['y_length'] = self.traffic_light_segments['upper_right'].y_length
                if self.traffic_light_segments['lower_left'] is not None:
                    args['x_length'] = self.traffic_light_segments['lower_left'].x_length

            # finally, create the new segment
            self.traffic_light_segments[self.sidewalk_position] = traffic_light(**args)

        return self.traffic_light_segments[self.sidewalk_position]


class simulation:
    # simulates a pedestrian traversing a city_map from upper_left to lower_right
    #     respecting city_map length restrictions and end-goal position
    #     respecting pedestrian choice_wait_time at traffic_lights, when able to choose not to wait
    # pedestrian will choose 

    def __init__(self):
        # state
        self.city_map = city_map()
        self.pedestrian = pedestrian()
        self.time = 0.0

        # logged data
        self.cumulative_time_waiting_at_lights = 0.0
        self.cumulative_lights_waited_at = 0

    def simulate(self):
        # checks for end state, executes simulation_step
        while self.city_map.end_reached != True:  # end_reached is 4-state, so explicit equation to True is necessary
            self.simulation_step()

    def simulation_step(self):
        # walks the pedestrian either across one length of a sidewalk, or across a traffic_light
        # tracks time taken in this step
        # demands new city_map segments when needed
        # logs simulation data
        # assumes is only called if end_reached is not True

        if self.city_map.sidewalk_position == 'upper_left':
            # must cross sidewalk in this position (no backtracking), but direction of cross is largely arbitrary
            # if end has been reached in one map direction, always choose the other direction to walk
            if not self.city_map.end_reached:
                direction = random.choice('xy')
            else:
                direction = other_direction[self.city_map.end_reached]

            if direction == 'x':
                destination = 'upper_right'
            else:
                destination = 'lower_left'

            self.cross_sidewalk(direction, destination)

        elif self.city_map.sidewalk_position == 'lower_left':
            # check if we can travel farther in y-direction
            if self.city_map.end_reached != 'y':
                # give pedestrian choice to wait for light to change (or cross immediately if able)
                light = self.city_map.get_current_traffic_light()
                light.set_state(self.time)  # update cycle information
                cross_wait_time = light.time_until_can_cross('y', self.pedestrian.velocity)

                if self.pedestrian.would_choose_to_wait_for_light(cross_wait_time):
                    self.time += cross_wait_time
                    self.cumulative_time_waiting_at_lights += cross_wait_time
                    self.cumulative_lights_waited_at += 1
                    self.cross_traffic_light('y')
                    return

            # otherwise go to the remaining corner
            self.cross_sidewalk('x', 'lower_right')

        elif self.city_map.sidewalk_position == 'upper_right':
            # check if we can travel farther in y-direction
            if self.city_map.end_reached != 'x':
                # give pedestrian choice to wait for light to change (or cross immediately if able)
                light = self.city_map.get_current_traffic_light()
                light.set_state(self.time)  # update cycle information
                cross_wait_time = light.time_until_can_cross('x', self.pedestrian.velocity)

                if self.pedestrian.would_choose_to_wait_for_light(cross_wait_time):
                    self.time += cross_wait_time
                    self.cumulative_time_waiting_at_lights += cross_wait_time
                    self.cumulative_lights_waited_at += 1
                    self.cross_traffic_light('x')
                    return

            # otherwise go to the remaining corner
            self.cross_sidewalk('y', 'lower_right')

        else:  # lower_right corner
            # must cross traffic_light in this position (no backtracking), but direction of cross is largely arbitrary
            #     if end has been reached in one map direction, always choose the other direction to walk
            #     otherwise choose the direction with a shorter wait time

            light = self.city_map.get_current_traffic_light()
            light.set_state(self.time)  # update cycle information
            cross_wait_time_x = light.time_until_can_cross('x', self.pedestrian.velocity)
            cross_wait_time_y = light.time_until_can_cross('y', self.pedestrian.velocity)

            # choose direction of travel
            if self.city_map.end_reached:
                direction = other_direction[self.city_map.end_reached]
            else:
                if cross_wait_time_x <= cross_wait_time_y:
                    direction = 'x'
                else:
                    direction = 'y'

            if direction == 'x':
                cross_wait_time = cross_wait_time_x
            else:
                cross_wait_time = cross_wait_time_y

            # wait for crossing availability, and finally execute crossing
            self.time += cross_wait_time
            self.cumulative_time_waiting_at_lights += cross_wait_time
            self.cumulative_lights_waited_at += 1
            self.cross_traffic_light(direction)

    def cross_sidewalk(self, direction, destination):
        # calculate time spent
        self.time += self.city_map.sidewalk_segment.time_to_cross(direction, self.pedestrian.velocity)

        # update map position
        self.city_map.sidewalk_position = destination

    def cross_traffic_light(self, direction):
        # calculate time spent
        self.time += self.city_map.get_current_traffic_light().time_to_cross(direction, self.pedestrian.velocity)

        # generate new sidewalk_block
        self.city_map.new_sidewalk_block(direction)


class monte_carlo:
    def __init__(self):
        self.log = defaultdict(list)

    def run_simulations(self, n=50):
        for _ in range(n):
            # execute simulation
            sim = simulation()
            sim.simulate()

            # accumulate data
            self.log['choice_wait_time'].append(sim.pedestrian.choice_wait_time)
            self.log['cumulative_time_waiting_per_light'].append(sim.cumulative_time_waiting_at_lights / sim.cumulative_lights_waited_at)

    def plot(self):
        # plot accumulated data
        plt.scatter(self.log['choice_wait_time'], self.log['cumulative_time_waiting_per_light'], marker='x', s=2, color='red')
        plt.xlabel('choice_wait_time')
        plt.ylabel('cumulative_time_waiting_per_light')
        plt.show()


class Tests:
    def test_traffic_light(self):
        light = traffic_light(x_length=3, y_length=5, x_signal_duration=7, y_signal_duration=11, initial_state=0.5)

        assert light.state == 0.5
        light.set_state(0)
        assert light.state == 0.5
        light.set_state(18)
        assert light.state == 0.5
        light.set_state(21.5)
        assert light.state == 1

        light.set_initial_time_offset(initial_state = 0.9)
        light.set_state(0)
        assert light.state == 0.9

        light.set_initial_time_offset(initial_state = 1.9)
        light.set_state(0)
        assert light.state == 1.9

        light.set_initial_time_offset(initial_state = 0.5)
        light.set_state(0)
        assert light.current_crossing_direction() == 'x'

        light.set_initial_time_offset(initial_state = 1.5)
        light.set_state(0)
        assert light.current_crossing_direction() == 'y'

        light.set_initial_time_offset(initial_state = 1)
        light.set_state(0)
        assert light.current_crossing_direction() == 'y'

        light.set_initial_time_offset(initial_state = 0.5)
        light.set_state(0)

        assert light.time_to_cross('x', 2) == 1.5
        assert light.time_to_cross('y', 2) == 2.5

        assert light.current_crossing_direction() == 'x'
        light.set_state(4.5 + 19*3)
        assert light.current_crossing_direction() == 'y'
        light.set_state(16)
        assert light.current_crossing_direction() == 'x'

        assert light.time_until_switch_directions() == 5.5
        assert light.time_until_switch_directions_twice() == 16.5
        light.set_state(4.5)
        assert light.time_until_switch_directions() == 10
        assert light.time_until_switch_directions_twice() == 17

        assert light.enough_time_to_cross('y', 1) == True
        assert light.enough_time_to_cross('y', 0.1) == False

        assert light.time_until_can_cross('y', 1) == 0
        assert light.time_until_can_cross('x', 1) == 10
        assert light.time_until_can_cross('y', 0.1) == 17

    def test_sidewalk_block(self):
        sb = sidewalk_block(x_length=3, y_length=5)

        assert sb.time_to_cross('x', 1) == 3
        assert sb.time_to_cross('x', 0.5) == 6
        assert sb.time_to_cross('y', 2.5) == 2

    def test_pedestrian(self):
        p = pedestrian(velocity=3, choice_wait_time=5)

        assert p.would_choose_to_wait_for_light(3) == True
        assert p.would_choose_to_wait_for_light(6) == False

    def test_city_map(self):
        cm = city_map(x_length=3, y_length=5)

        # test initial state
        assert cm.grid_position['x'] == 1
        assert cm.grid_position['y'] == 1
        assert cm.sidewalk_position == 'upper_left'
        assert cm.end_reached == False

        # test new traffic_lights
        cm.sidewalk_position = 'upper_right'
        light_ur = cm.get_current_traffic_light()
        for loc, segment in cm.traffic_light_segments.items():
            if loc == 'upper_right':
                assert segment == light_ur
            else:
                assert segment is None

        cm.get_current_traffic_light()

        cm.sidewalk_position = 'lower_left'
        light_ll = cm.get_current_traffic_light()
        for loc, segment in cm.traffic_light_segments.items():
            if loc == 'upper_right':
                assert segment == light_ur
            elif loc == 'lower_left':
                assert segment == light_ll
            else:
                assert segment is None

        cm.sidewalk_position = 'upper_left'
        light_ul = cm.get_current_traffic_light()
        for loc, segment in cm.traffic_light_segments.items():
            if loc == 'upper_right':
                assert segment == light_ur
            elif loc == 'lower_left':
                assert segment == light_ll
            elif loc == 'upper_left':
                assert segment == light_ul
            else:
                assert segment is None

        cm.sidewalk_position = 'lower_right'
        light_lr = cm.get_current_traffic_light()
        for loc, segment in cm.traffic_light_segments.items():
            if loc == 'upper_right':
                assert segment == light_ur
            elif loc == 'lower_left':
                assert segment == light_ll
            elif loc == 'upper_left':
                assert segment == light_ul
            else:
                assert segment == light_lr

        # test same light lengths
        assert light_ul.y_length == light_ur.y_length
        assert light_ur.x_length == light_lr.x_length
        assert light_lr.y_length == light_ll.y_length
        assert light_ll.x_length == light_ul.x_length

        # test creating new sidewalk_blocks
        sb = cm.sidewalk_segment
        cm.new_sidewalk_block('x')

        sb2 = cm.sidewalk_segment
        assert sb.y_length == sb2.y_length
        assert cm.grid_position['x'] == 2
        assert cm.grid_position['y'] == 1

        assert cm.traffic_light_segments['upper_left'] == light_ur
        assert cm.traffic_light_segments['lower_left'] == light_lr
        assert cm.traffic_light_segments['lower_right'] == None
        assert cm.traffic_light_segments['lower_right'] == None

        cm.new_sidewalk_block('y')

        sb3 = cm.sidewalk_segment
        assert sb2.x_length == sb3.x_length
        assert cm.grid_position['x'] == 2
        assert cm.grid_position['y'] == 2

        assert cm.traffic_light_segments['upper_left'] == light_lr
        assert cm.traffic_light_segments['lower_left'] == None
        assert cm.traffic_light_segments['lower_right'] == None
        assert cm.traffic_light_segments['lower_right'] == None

        # test end_reached
        assert cm.end_reached == False

        cm.new_sidewalk_block('x')
        assert cm.end_reached == 'x'

        cm.new_sidewalk_block('y')
        assert cm.end_reached == 'x'
        cm.new_sidewalk_block('y')
        assert cm.end_reached == 'x'
        cm.new_sidewalk_block('y')
        assert cm.end_reached == True

        cm = city_map(x_length=5, y_length=3)
        cm.new_sidewalk_block('y')
        assert cm.end_reached == False
        cm.new_sidewalk_block('y')
        assert cm.end_reached == 'y'

        # test sidewalk position when creating new sidewalk_blocks
        cm = city_map(x_length=5, y_length=3)

        cm.sidewalk_position = 'upper_right'
        cm.new_sidewalk_block('y')
        assert cm.sidewalk_position == 'upper_left'

        cm.sidewalk_position = 'lower_left'
        cm.new_sidewalk_block('x')
        assert cm.sidewalk_position == 'upper_left'

        cm.sidewalk_position = 'lower_right'
        cm.new_sidewalk_block('x')
        assert cm.sidewalk_position == 'lower_left'

        cm.sidewalk_position = 'lower_right'
        cm.new_sidewalk_block('y')
        assert cm.sidewalk_position == 'upper_right'

    def test_simulation(self):
        # test sidewalk crossing
        sim = simulation()
        sim.pedestrian.velocity = 2
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13

        assert sim.city_map.sidewalk_position == 'upper_left'
        assert sim.time == 0

        sim.cross_sidewalk('x', 'upper_right')
        assert sim.city_map.sidewalk_position == 'upper_right'
        assert sim.time == 3.5

        sim.cross_sidewalk('y', 'lower_right')
        assert sim.city_map.sidewalk_position == 'lower_right'
        assert sim.time == 10

        # test traffic_light crossing
        sim = simulation()
        sim.pedestrian.velocity = 2
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5

        sim.city_map.sidewalk_position = 'upper_right'
        light = sim.city_map.get_current_traffic_light()
        light.x_length = 7
        light.y_length = 13
        sb = sim.city_map.sidewalk_segment
        sim.cross_traffic_light('x')
        assert sim.time == 3.5
        assert sim.city_map.sidewalk_position == 'upper_left'
        assert sb != sim.city_map.sidewalk_segment

        sim.city_map.sidewalk_position = 'lower_right'
        light = sim.city_map.get_current_traffic_light()
        light.x_length = 17
        light.y_length = 19
        sb = sim.city_map.sidewalk_segment
        sim.cross_traffic_light('y')
        assert sim.time == 13
        assert sim.city_map.sidewalk_position == 'upper_right'
        assert sb != sim.city_map.sidewalk_segment

        # test simulation_step - upper_left
        sim = simulation()
        sim.pedestrian.velocity = 2
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sb = sim.city_map.sidewalk_segment

        sim.city_map.end_reached = 'y'
        sim.simulation_step()
        assert sim.city_map.sidewalk_position == 'upper_right'
        assert sim.time == 3.5
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 0
        assert sb == sim.city_map.sidewalk_segment

        sim.city_map.sidewalk_position = 'upper_left'
        sim.city_map.end_reached = 'x'
        sim.simulation_step()
        assert sim.city_map.sidewalk_position == 'lower_left'
        assert sim.time == 10
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 0
        assert sb == sim.city_map.sidewalk_segment

        sim = simulation()
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sb = sim.city_map.sidewalk_segment
        sim.simulation_step()
        assert sim.city_map.sidewalk_position in ['lower_left', 'upper_right']
        assert sb == sim.city_map.sidewalk_segment

        # test simulation_step - lower_left
        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 99
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_left'
        sim.city_map.end_reached = 'y'
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 1)
        sim.simulation_step()
        assert sb == sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'lower_right'
        assert sim.time == 31.5
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 0

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 0
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_left'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 0)
        sim.simulation_step()
        assert sb == sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'lower_right'
        assert sim.time == 31.5
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 0

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 99
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_left'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 0)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'upper_left'
        assert sim.time == 50.5
        assert sim.cumulative_time_waiting_at_lights == 11
        assert sim.cumulative_lights_waited_at == 1

        # test simulation_step - upper_right
        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 99
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'upper_right'
        sim.city_map.end_reached = 'x'
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 0)
        sim.simulation_step()
        assert sb == sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'lower_right'
        assert sim.time == 34.5
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 0

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 0
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'upper_right'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 1)
        sim.simulation_step()
        assert sb == sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'lower_right'
        assert sim.time == 34.5
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 0

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 99
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'upper_right'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 1)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'upper_left'
        assert sim.time == 54.5
        assert sim.cumulative_time_waiting_at_lights == 17
        assert sim.cumulative_lights_waited_at == 1

        # test simulation_step - lower_right
        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 99
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_right'
        sim.city_map.end_reached = 'x'
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 0)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'upper_right'
        assert sim.time == 50.5
        assert sim.cumulative_time_waiting_at_lights == 11
        assert sim.cumulative_lights_waited_at == 1

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 99
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_right'
        sim.city_map.end_reached = 'y'
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 1)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'lower_left'
        assert sim.time == 54.5
        assert sim.cumulative_time_waiting_at_lights == 17
        assert sim.cumulative_lights_waited_at == 1

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 0
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_right'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 0)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'lower_left'
        assert sim.time == 37.5
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 1

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 0
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_right'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 1)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'upper_right'
        assert sim.time == 39.5
        assert sim.cumulative_time_waiting_at_lights == 0
        assert sim.cumulative_lights_waited_at == 1

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 0
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_right'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 1.9)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'lower_left'
        assert abs(sim.cumulative_time_waiting_at_lights - 1.7) < 0.00001
        assert sim.time == 39.2
        assert sim.cumulative_lights_waited_at == 1

        sim = simulation()
        sim.time = 28
        sim.pedestrian.velocity = 2
        sim.pedestrian.choice_wait_time = 0
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sim.city_map.sidewalk_segment.x_length = 7
        sim.city_map.sidewalk_segment.y_length = 13
        sim.city_map.sidewalk_position = 'lower_right'
        sim.city_map.end_reached = False
        sb = sim.city_map.sidewalk_segment
        light = sim.city_map.get_current_traffic_light()
        light.x_signal_duration = 11
        light.y_signal_duration = 17
        light.x_length = 19
        light.y_length = 23
        light.set_initial_time_offset(initial_state = 0.9)
        sim.simulation_step()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.sidewalk_position == 'upper_right'
        assert sim.time == 40.6
        assert abs(sim.cumulative_time_waiting_at_lights- 1.1) < 0.00001
        assert sim.cumulative_lights_waited_at == 1

        # test simulation
        sim = simulation()
        sim.city_map.length['x'] = 3
        sim.city_map.length['y'] = 5
        sb = sim.city_map.sidewalk_segment
        sim.simulate()
        assert sb != sim.city_map.sidewalk_segment
        assert sim.city_map.end_reached == True
        assert sim.city_map.grid_position['x'] == 3
        assert sim.city_map.grid_position['y'] == 5

    def test_monte_carlo(self):
        # check for correct number of outputs, and sanity check bounds
        for n in [1, 7, 101]:
            mc = monte_carlo()
            mc.run_simulations(n=n)
            assert len(mc.log['choice_wait_time']) == n
            assert len(mc.log['cumulative_time_waiting_per_light']) == n
            for x in mc.log['choice_wait_time']:
                assert WAIT_TIME[0] <= x <= WAIT_TIME[1]
            for x in mc.log['cumulative_time_waiting_per_light']:
                assert x <= CROSSWALK_DURATION[1] * 2

    def test_initialization_randoms(self):
        # TODO execute random init functions, but don't test output
        # traffic_light()
        # sidewalk_block()
        # pedestrian()
        # city_map()
        # simulation()

        # TODO
        # sim.simulate()

        # TODO
        # mc.plot()
        pass


if __name__ == '__main__':
    mc = monte_carlo()
    mc.run_simulations(n=1000)
    mc.plot()

# pytest --cov=. crosswalk-simulator.py
