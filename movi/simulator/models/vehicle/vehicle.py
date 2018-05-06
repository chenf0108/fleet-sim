from common import vehicle_status_codes
from .vehicle_state import VehicleState
from .vehicle_behavior import Occupied, Cruising, Idle, Assigned, OffDuty
from logger import sim_logger
from logging import getLogger

class Vehicle(object):
    behavior_models = {
        vehicle_status_codes.IDLE: Idle(),
        vehicle_status_codes.OCCUPIED: Occupied(),
        vehicle_status_codes.CRUISING: Cruising(),
        vehicle_status_codes.ASSIGNED: Assigned(),
        vehicle_status_codes.OFF_DUTY: OffDuty()
    }

    def __init__(self, vehicle_state, num_seats=4):
        if not isinstance(vehicle_state, VehicleState):
            raise ValueError
        self.state = vehicle_state
        self.__behavior = self.behavior_models[vehicle_state.status]
        self.__num_seats = num_seats
        self.__customers = []
        self.__route_plan = []
        self.earnings = 0


    # state changing methods
    def step(self, timestep):
        if self.__behavior.available:
            self.state.idle_duration += timestep
        else:
            self.state.idle_duration = 0

        try:
            self.__behavior.step(self, timestep)
        except:
            logger = getLogger(__name__)
            logger.error(self.state.to_msg())
            raise

        sim_logger.log_vehicle_event("step", self.state.to_msg())

    def cruise(self, route, triptime, speed):
        assert self.__behavior.available
        self.__reset_plan()
        self.__set_route(route, speed)
        self.__set_destination(route[-1], triptime)
        self.__change_to_cruising()
        sim_logger.log_vehicle_event("cruise", self.state.to_msg())
        # sim_logger.log_command("cruise", self.get_id(), route[-1])

    def head_for_customer(self, destination, triptime, customer_id):
        assert self.__behavior.available
        self.__reset_plan()
        self.__set_destination(destination, triptime)
        self.state.assigned_customer_id = customer_id
        self.__change_to_assigned()
        sim_logger.log_vehicle_event("head_for_customer", self.state.to_msg())
        # sim_logger.log_command("head_for_customer", self.get_id(), customer_id)

    def take_rest(self, duration):
        assert self.__behavior.available
        self.__reset_plan()
        self.state.idle_duration = 0
        self.__set_destination(self.get_location(), duration)
        self.__change_to_off_duty()
        sim_logger.log_vehicle_event("take_rest", self.state.to_msg())

    def pickup(self, customer):
        assert self.get_location() == customer.get_origin()
        customer.ride_on()
        customer_id = customer.get_id()
        self.__customers.append(customer)
        self.__reset_plan() # For now we don't consider routes of occupied trip
        self.state.assigned_customer_id = customer_id
        self.__set_destination(customer.get_destination(), customer.get_trip_duration())
        self.__change_to_occupied()
        sim_logger.log_vehicle_event("pickup", self.state.to_msg())

    def dropoff(self):
        assert len(self.__customers) > 0
        assert self.get_location() == self.__customers[0].get_destination_road()
        customer = self.__customers.pop(0)

        self.__reset_plan()
        self.__change_to_idle()
        self.earnings += customer.make_payment()
        sim_logger.log_vehicle_event("dropff", self.state.to_msg())
        return customer

    def park(self):
        self.__reset_plan()
        self.__change_to_idle()
        sim_logger.log_vehicle_event("park", self.state.to_msg())

    def update_location(self, location, route):
        self.state.location = location
        self.__route_plan = route

    def update_time_to_destination(self, timestep):
        self.state.time_to_destination = max(self.state.time_to_destination - timestep, 0)
        if self.state.time_to_destination <= 0:
            self.state.time_to_destination = 0
            self.state.location = self.state.destination
            return True
        else:
            return False

    # some getter methods
    def get_id(self):
        vehicle_id = self.state.id
        return vehicle_id

    def get_location(self):
        location = self.state.lat, self.state.lon
        return location

    def get_destination(self):
        destination = self.state.destination_lat, self.state.destination_lon
        return destination

    def get_speed(self):
        speed = self.state.speed
        return speed

    def get_assigned_customer_id(self):
        customer_id = self.state.assigned_customer_id
        return customer_id

    def get_route(self):
        return self.__route_plan[:]

    def get_idle_duration(self):
        duration = self.state.idle_duration
        return duration

    def get_state(self):
        state = []
        for attr in self.state.__slots__:
            state.append(getattr(self.state, attr))
        return state

    def __reset_plan(self):
        self.state.reset_plan()
        self.__route_plan = []

    def __set_route(self, route, speed):
        assert self.state.location == route[0]
        self.__route_plan = route
        self.state.speed = speed

    def __set_destination(self, destination, triptime):
        self.state.destination = destination
        self.state.time_to_destination = triptime


    def __change_to_idle(self):
        self.__change_behavior_model(vehicle_status_codes.IDLE)

    def __change_to_cruising(self):
        self.__change_behavior_model(vehicle_status_codes.CRUISING)

    def __change_to_assigned(self):
        self.__change_behavior_model(vehicle_status_codes.ASSIGNED)

    def __change_to_occupied(self):
        self.__change_behavior_model(vehicle_status_codes.OCCUPIED)

    def __change_to_off_duty(self):
        self.__change_behavior_model(vehicle_status_codes.OFF_DUTY)

    def __change_behavior_model(self, status):
        self.__behavior = self.behavior_models[status]
        self.state.status = status