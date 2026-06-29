package edu.penn.rtg.schedulingapp;

import java.io.FileWriter;
import java.util.HashMap;


/**
 * The SchedulingTree class is the basic building block of the tool. It contains
 * a tree structure of a relation between Scheduling Components and Tasks.
 */
public class SchedulingTree {
	// Root of the tree
	private TreeComponent root;

	// Map of components of all Scheduling Components of the tree
	private HashMap<String, TreeComponent> components;
	
	/**
	 * A default Tree
	 */
	public SchedulingTree() {
		super();
		root = new TreeComponent("OS Scheduler",null);
		components = new HashMap<String, TreeComponent>();
	}

	/**
	 * A tree is being constructed from a given XML file
	 * 
	 * @param root
	 *            Root Component
	 */
	public SchedulingTree(TreeComponent root) {
		super();
		this.root = root;
		components = new HashMap<String, TreeComponent>();
	}

	/**
	 * Returns all the components in the Tree
	 */
	public HashMap<String, TreeComponent> getMap() {
		return components;
	}

	/**
	 * Add a new Scheduling Component to the tree
	 * 
	 * @param child
	 *            A new child Scheduling Component
	 * @param parent
	 *            The parent to which the child needs to be added
	 * @throws Exception
	 *             When Min and Max periods for parent are different, then child
	 *             needs to have same values for them as the parent. If this
	 *             rule is not followed, Exception will be thrown.
	 */
	public void addComponent(TreeComponent child,
			TreeComponent parent) {
		/*
		if (root.getMinPeriod() != root.getMaxPeriod()) {
			if ((child.getMaxPeriod() != root.getMaxPeriod())
					|| (child.getMinPeriod() != root.getMinPeriod())) {
				throw new Exception();
			}
		}
		*/
		parent.addChild(child);
		child.setParentComp(parent);
		components.put(child.getCompName(),  child);
	}

	/**
	 * Remove a given Scheduling Component from the tree
	 * 
	 * @param parent
	 *            Parent of the child which is to be removed
	 * @param child
	 *            Component to be removed
	 */
	public void removeComponent(TreeComponent parent,
			TreeComponent child) {
		child.removeFromParent();
		parent.removeChild(child);
		components.remove(child.getCompName());
	}

	/**
	 * Add the task into the given Scheduling Component
	 * 
	 * @param parent
	 *            Scheduling Component to which the new task needs to be added
	 * @param task
	 * 
	 */
	public void addTask(TreeComponent parent, Task task){
		parent.getTaskList().addToList(task);
	}
	/**
	 * Returns the Root Component of the Tree
	 * 
	 * @return
	 */
	public TreeComponent getRoot() {
		return root;
	}

	/**
	 * Write the entire tree to the given XML file
	 * 
	 * @param fileName
	 *            Pathname of the file to which the Scheduling Tree needs to be
	 *            written
	 */
	public void convertToXML(String fileName) {
		try {
			FileWriter outputStream = new FileWriter(fileName);
			StringBuffer buffer = new StringBuffer();

			root.getSchCom().convertToXML(buffer);
			outputStream.write(buffer.toString());
			outputStream.close();
		} catch (Exception e) {
			System.err.println("Error in writing to file");
		}
	}


}
