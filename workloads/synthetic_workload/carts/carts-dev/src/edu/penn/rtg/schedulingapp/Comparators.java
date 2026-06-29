package edu.penn.rtg.schedulingapp;

import java.util.*;
/**
 * Comparator for ordering task.
 * Return comparator of tasks with the order of deadline ascending.
 * <P>
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class Comparators {

	/**
	 * Return comparator depending on deadline 
	 * @return      comparator with the order of deadline ascending 
	 * @see         Comparator
	 */
	public static Comparator<Task> DeadlineAscending() {
		return new Comparator<Task>() {
			public int compare(Task t1, Task t2) {
				return (t1.getDeadline() < t2.getDeadline() ? -1 : (t1
						.getDeadline() == t2.getDeadline() ? 0 : 1));
			}
		};
	}
}
