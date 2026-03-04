from mrws.exceptions import SimulationError


def simple_single_robot_schedule(self, fault_tolerant_mode, single_item_mode=False):
    if fault_tolerant_mode:
        self.reassign_orders_if_faulted()

    orders_to_move = []
    # For every order in the backlog (sorted by priority)
    for order_obj in reversed(sorted(self._orders_backlog, key=lambda order1: order1.get_prio())):

        free_robots = self.find_free_robots(fault_tolerant_mode)
        if not free_robots:
            free_robot_obj = None
        else:
            free_robot_obj = free_robots[0]

        free_goal_obj = self.find_goal_for_order(order_obj)

        if (free_robot_obj is not None) and (free_goal_obj is not None):
            self.assign_single_robot_schedule_empty_starting_inventory(order_obj,
                                                                       free_robot_obj,
                                                                       free_goal_obj,
                                                                       single_item_mode)
            orders_to_move.append(order_obj)

    for ordr in orders_to_move:
        self._orders_backlog.remove(ordr)
        self._orders_active.append(ordr)
    return orders_to_move

def single_interrupt_robot_schedule(self, fault_tolerant_mode):
    if fault_tolerant_mode:
        self.reassign_orders_if_faulted()

    orders_to_move = []
    for order_obj in reversed(sorted(self._orders_backlog, key=lambda order1: order1.get_prio())):
        free_robots = self.find_free_robots(fault_tolerant_mode)
        if not free_robots:
            free_robot_obj = None
        else:
            free_robot_obj = free_robots[0]

        free_goal_obj = self.find_goal_for_order(order_obj)

        if (free_robot_obj is not None) and (free_goal_obj is not None):
            self.assign_single_robot_schedule_empty_starting_inventory(order_obj, free_robot_obj, free_goal_obj)
            orders_to_move.append(order_obj)

        elif free_robot_obj is None and free_goal_obj is not None:
            found_lower_prio_robot_name = None
            lowest_prio_found = order_obj.get_prio()

            for order_id, robot_names in self._order_robots_assignment.items():
                if len(robot_names) != 1:
                    raise SimulationError("Only one robot should be assigned to each order for this scheduling type")
                robot_obj = self._robots[robot_names[0]]
                robot_prio = robot_obj.get_prio()

                if robot_prio < lowest_prio_found:
                    target_good = False
                    inventory_usage_good = False

                    if robot_obj.get_target() is None:
                        target_good = True
                    else:
                        # We don't want a robot with a shelf as its target as its inventory size will increase
                        # by one and invalidate the following calculations
                        if "shelf" not in robot_obj.get_target().get_name():
                            target_good = True

                    if robot_obj.get_inventory_usage() != 0:
                        if robot_obj.get_inventory_usage() != self._ROBOT_INVENTORY_SIZE:
                            if order_obj.get_highest_item_dep() <= robot_obj.peek_inventory().get_dependency():
                                inventory_usage_good = True
                    else:
                        inventory_usage_good = True

                    if inventory_usage_good and target_good:
                        lowest_prio_found = robot_prio
                        found_lower_prio_robot_name = robot_names[0]

            if found_lower_prio_robot_name is not None:
                selected_bot = self._robots[found_lower_prio_robot_name]
                self._order_robots_assignment[order_obj.get_id()] = [found_lower_prio_robot_name]
                self._assign_robot_to_order(found_lower_prio_robot_name, order_obj.get_id())
                selected_bot.set_prio(order_obj.get_prio())
                self._order_goal_assignment[order_obj.get_id()] = free_goal_obj.get_name()

                robot_inventory_already_used = selected_bot.get_inventory_usage()

                prepend_schedule = []
                robot_inventory_used_for_this_order = 0
                for item in reversed(sorted(order_obj.get_items(), key=lambda itm: itm.get_dependency())):
                    if item.get_name() not in self._item_to_shelf_mapping.keys():
                        message = "Scheduling impossible, no shelf exists for item %s" % item.get_name()
                        raise SimulationError(message)
                    shelf_name = self._item_to_shelf_mapping[item.get_name()][0]
                    if robot_inventory_used_for_this_order == self._ROBOT_INVENTORY_SIZE - robot_inventory_already_used:
                        prepend_schedule.append("%s|%s" % (free_goal_obj.get_name(),
                                                           robot_inventory_used_for_this_order))
                        robot_inventory_used_for_this_order = 0
                    prepend_schedule.append(shelf_name)
                    robot_inventory_used_for_this_order = robot_inventory_used_for_this_order + 1

                prepend_schedule.append("%s|%s" % (free_goal_obj.get_name(), robot_inventory_used_for_this_order))

                self.prepend_to_schedule(found_lower_prio_robot_name, prepend_schedule)

                orders_to_move.append(order_obj)

    for ordr in orders_to_move:
        self._orders_backlog.remove(ordr)
        self._orders_active.append(ordr)
    return orders_to_move
