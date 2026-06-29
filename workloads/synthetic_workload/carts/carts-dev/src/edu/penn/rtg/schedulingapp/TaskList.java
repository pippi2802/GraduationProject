package edu.penn.rtg.schedulingapp;

import java.util.ArrayList;

import edu.penn.rtg.schedulingapp.old.ComponentSubUnit;
/**
 * Array List of Task class
 */
public class TaskList {

	private ArrayList<Task> tasks;

	/**
	 * Create a Task list
	 * 
	 */
	public TaskList() {
		tasks = new ArrayList<Task>();
	}

	/**
	 * Create a Task list
	 * @param listData array of Task 
	 */

	public TaskList(Task[] listData) {
		tasks = new ArrayList<Task>();
		for (int i = 0; i < listData.length; i++) {
			tasks.add(listData[i]);
		}
	}

	/**
	 *  Add given task to list
	 * 
	 * @param t given task
	 */

	public void addToList(Task t) {
		tasks.add(t);
		//System.out.println(tasks);
		//Collections.sort(tasks, Comparators.DeadlineAscending());
	}
	/**
	 *  Remove given task from list
	 * 
	 * @param t given task
	 */

	public void removeFromList(Task t) {
		tasks.remove(t);
		//Collections.sort(tasks, Comparators.DeadlineAscending());
	}

	/**
	 *  Return array list of tasks
	 * 
	 * @return      array list of tasks
	 */
	public ArrayList<Task> getTasks() {
		return tasks;
	}

	ArrayList<Task> getTaskArray() {
		return tasks;
	}

	/**
	 *  Return whether this component is RBT (Recursive Branching Tree) 
	 * 
	 * @return  boolean    
	 */

	public boolean isRBT() {
		return false;
	}

	/**
	 * Writes fields of Tasks  in list into the given buffer
	 */
	void convertToXML(StringBuffer buffer) {
		for (int i = 0; i < tasks.size(); i++) {
			tasks.get(i).convertToXML(buffer);
		}
	}

	/**
	 *  Return contents of tasks in list 
	 *  Used to display the task information in GUI
	 * 
	 * @return      attributes of tasks in list
	 */

	public String toString() {
		StringBuffer buffer = new StringBuffer();
		for (int i = 0; i < tasks.size(); i++) {
			if(!tasks.get(i).getResult().isEmpty()){
				System.out.println("task's exec=: "+tasks.get(i).getExecution()+" \n");
				buffer.append(tasks.get(i).getResult());
				buffer.append("\n");
				System.out.println("tasks.get(i).getResult()=" + tasks.get(i).getResult() + "\n");
			}	
		}
		return buffer.toString();
	}
}
