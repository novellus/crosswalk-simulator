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
        self.initial_state = initial_state or self.random_state()
        self.state = self.initial_state

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
        mid_cycle_time = time % (self.x_signal_duration + self.y_signal_duration)

        if mid_cycle_time < self.x_signal_duration:  # x-crossing
            self.state = mid_cycle_time / self.x_signal_duration
        else:   # y-crossing
            self.state = 1 + (mid_cycle_time - self.x_signal_duration) / self.y_signal_duration

        assert 0 <= self.state < 2

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
        # generates new sidewalk_block in specified direction
        # sets sidewalk_position on new block
        # tracks grid size restrictions
        # handles propogation of attached traffic_lights

        self.sidewalk_segment = sidewalk_block()

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

                if self.pedestrian.choice_wait_time <= cross_wait_time:
                    self.time += cross_wait_time
                    self.cumulative_time_waiting_at_lights += cross_wait_time
                    self.cumulative_lights_waited_at += 1
                    self.cross_traffic_light('y', 'upper_right')
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

                if self.pedestrian.choice_wait_time <= cross_wait_time:
                    self.time += cross_wait_time
                    self.cumulative_time_waiting_at_lights += cross_wait_time
                    self.cumulative_lights_waited_at += 1
                    self.cross_traffic_light('x', 'upper_right')
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

            # assign destination, cross_wait_time
            if direction == 'x':
                destination = 'lower_left'
                cross_wait_time = cross_wait_time_x
            else:
                destination = 'upper_right'
                cross_wait_time = cross_wait_time_y

            # wait for crossing availability, and finally execute crossing
            self.time += cross_wait_time
            self.cumulative_time_waiting_at_lights += cross_wait_time
            self.cumulative_lights_waited_at += 1
            self.cross_traffic_light(direction, destination)


    def cross_sidewalk(self, direction, destination):
        # update map position
        self.city_map.sidewalk_position = destination

        # calculate time spent
        self.time += self.city_map.sidewalk_segment.time_to_cross(direction, self.pedestrian.velocity)

    def cross_traffic_light(self, direction, destination):
        # generate new sidewalk_block
        self.city_map.new_sidewalk_block(direction)

        # update map position
        self.city_map.sidewalk_position = destination

        # calculate time spent
        self.time += self.city_map.get_current_traffic_light().time_to_cross(direction, self.pedestrian.velocity)


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


if __name__ == '__main__':
    mc = monte_carlo()
    mc. run_simulations(n=1000)
    mc.plot()
