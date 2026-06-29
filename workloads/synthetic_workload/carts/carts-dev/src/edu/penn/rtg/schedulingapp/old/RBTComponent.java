package edu.penn.rtg.schedulingapp.old;

import java.awt.geom.Line2D;
import java.util.HashMap;
import java.util.Map;

import edu.penn.rtg.schedulingapp.ResourceModelList;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.TaskList;

/**
 * Currently not used, but represents RBT (Recursive Branching Tree) components.
 * Will probably need editing when RBT functionality is added to the program.
 * 
 */
public class RBTComponent {
	private HashMap<String, RBTComponent> children;
	private String name;
	private RBTComponent parent;
	private TaskList taskList;
	private Line2D.Double connector;
	public boolean isHighlighted = false;
	private String algorithm;
	private ComponentSubUnit sub;
	private double minPeriod, maxPeriod;

	public RBTComponent() {
		name = "";
		parent = null;
		children = new HashMap<String, RBTComponent>();
		taskList = new TaskList();
	}

	public RBTComponent(String name) {
		this.name = name;
		parent = null;
		children = new HashMap<String, RBTComponent>();
		taskList = new TaskList();
	}

	public RBTComponent(String name, RBTComponent parent) {
		this.name = name;
		this.parent = parent;
		children = new HashMap<String, RBTComponent>();
		taskList = new TaskList();
	}

	public RBTComponent(RBTComponent parent) {
		this.name = parent.name + " jr.";
		this.parent = parent;
		children = new HashMap<String, RBTComponent>();
		taskList = new TaskList();
	}

	public void addChild(RBTComponent child) {
		children.put(child.getName(), child);
	}

	public RBTComponent getChild(String name) {
		return children.get(name);
	}

	public boolean hasParent() {
		return parent != null;
	}

	public boolean hasChildren() {
		return children.size() > 0;
	}

	public boolean isFixed() {
		return false;
	}

	public String getName() {
		return name;
	}

	public void setName(String name) {
		this.name = name;
	}

	public void removeChild(RBTComponent child) {
		children.remove(child.getName());
	}

	public void setParent(RBTComponent parent) {
		this.parent = parent;
	}

	public Line2D.Double getLine2D() {
		return connector;
	}

	public TaskList getTaskList() {
		return taskList;
	}

	public void setTaskList(TaskList t) {
		taskList = t;
	}

	public boolean isHighlighted() {
		return isHighlighted;
	}

	public void setHighlighted(boolean b) {
		isHighlighted = b;
	}

	public void setAlgorithm(String alg) {
		algorithm = alg;
	}

	public String getAlgorithm() {
		return algorithm;
	}

	public void setSubUnit(ComponentSubUnit sub) {
		this.sub = sub;
		if (sub instanceof TaskList) {
			taskList = (TaskList) sub;
		}
	}

	public ComponentSubUnit getSubUnit() {
		return sub;
	}

	public void setMinPeriod(double d) {
		minPeriod = d;
	}

	public void setMaxPeriod(double d) {
		maxPeriod = d;
	}

	public Map<SchedulingComponent, TaskList> getChildrenToTaskTable() {
		throw new UnsupportedOperationException("Not supported yet.");
	}

	public TaskList getProcessedTaskList() {
		throw new UnsupportedOperationException("Not supported yet.");
	}

	public ResourceModelList getResourceModelList() {
		throw new UnsupportedOperationException("Not supported yet.");
	}

}
