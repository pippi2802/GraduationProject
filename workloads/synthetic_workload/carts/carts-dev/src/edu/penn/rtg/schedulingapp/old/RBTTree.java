package edu.penn.rtg.schedulingapp.old;

import java.awt.Graphics;
import java.util.ArrayList;
import java.util.HashMap;
import javax.swing.*;


/**
 * Generates a tree of RBT components and renders it visually. Is used to manage
 * the tree as well.
 * 
 */
public class RBTTree extends JPanel implements ComponentSubUnit {

	private RBTComponent root;
	private HashMap<String, RBTComponent> components;

	/**
	 * Constructor
	 * 
	 */

	public RBTTree() {
		super();
		root = new RBTComponent("root");
		components = new HashMap<String, RBTComponent>();
	}

	/**
	 * Constructor
	 * 
	 */

	public RBTTree(RBTComponent root) {
		super();
		this.root = root;
		components = new HashMap<String, RBTComponent>();
	}

	/**
	 * Duplicates a given RBDTree to allow for quicker productivity
	 * 
	 * @param previous
	 *            - the RBDTree one wishes to duplicate
	 */
	public RBTTree(RBTTree previous) {
		super();
		this.components = previous.components;
		this.root = previous.root;
	}
	/**
	 * Check whether it has root
	 * 
	 */

	public boolean hasRoot() {
		return root != null;
	}

	/**
	 * Check whether it is root
	 * 
	 */

	public boolean isRoot(RBTComponent possible) {
		return possible == root;
	}

	/**
	 * Add component to tree
	 * 
	 */

	void addComponent(RBTComponent child, RBTComponent parent) {
		parent.addChild(child);
		components.put(child.getName(), child);
	}

	/**
	 *  Return whether this component is RBT (Recursive Branching Tree) 
	 * 
	 * @return boolean
	 */

	public boolean isRBT() {
		return true;
	}

	/**
	 * Set component as root
	 * 
	 */


	public void setRoot(RBTComponent root) {
		this.root = (RBTComponent) root;
	}

	/**
	 * Return root component
	 * 
	 */

	public RBTComponent getRoot() {
		return root;
	}

	/**
	 * Return size of the tree
	 * 
	 */

	public int sizeOfTree() {
		return components.size() + 1;
	}

	/**
	 * Return specified component in the tree
	 * 
	 */

	public RBTComponent getComponentWithName(String name) {
		return components.get(name);
	}

	/**
	 * Set this component is not highelighted
	 * 
	 */

	public void resetHighlighted() {
		for (RBTComponent i : components.values()) {
			i.setHighlighted(false);
		}
	}

	/**
	 * Paint graphic
	 * 
	 */

	@Override
	public void paint(Graphics g) {
		update(g);
	}

	/**
	 * Return all component in the tree
	 * 
	 */

	Object[] getAllComponents() {
		ArrayList<RBTComponent> array = new ArrayList<RBTComponent>();
		array.add(root);
		array.addAll(components.values());

		return array.toArray();
	}
}
