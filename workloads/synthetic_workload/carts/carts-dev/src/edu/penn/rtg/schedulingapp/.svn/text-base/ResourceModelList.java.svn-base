package edu.penn.rtg.schedulingapp;

import java.util.ArrayList;
import javax.swing.JList;

import edu.penn.rtg.schedulingapp.old.ComponentSubUnit;

/**
 * Resource Model List. <P>
 * array list of Resource Model class
 * <P>
 * @author      
 * @version     1.0
 * @since       1.0
 */

public class ResourceModelList extends JList  {

	/**
	 * 
	 */
	private static final long serialVersionUID = 1L;
	private ArrayList<ResourceModel> resourceModels;
	/**
	 * Resource Model List Constructor
	 * 
	 */
	public ResourceModelList() {
		super();
		resourceModels = new ArrayList<ResourceModel>();
	}

	/**
	 * Resource Model List Constructor, it set array list of resource model
	 * 
	 * @param listData array of resource model to be set
	 */

	public ResourceModelList(ResourceModel[] listData) {
		super(listData);
		resourceModels = new ArrayList<ResourceModel>();
		for (int i = 0; i < listData.length; i++) {
			resourceModels.add(listData[i]);
		}
	}

	/**
	 *  Add a given resource model to list
	 * 
	 * @param t given resource model 
	 */
	public void addToList(ResourceModel t) {
		resourceModels.add(t);
		setListData(resourceModels.toArray());
	}

	/**
	 *  Remove a given resource model from list
	 * 
	 * @param t given resource model 
	 */

	public void removeFromList(ResourceModel t) {
		resourceModels.remove(t);
		setListData(resourceModels.toArray());
	}

	/**
	 *  Return array list of resource model
	 * 
	 * @return      array list of resource model
	 */

	public ArrayList<ResourceModel> getResourceModels() {
		return resourceModels;
	}

	/**
	 *  Update resource model list to screen
	 * 
	 * @return      none
	 */

	public void updateResourceModelList() {
		//System.out.println(resourceModels.toString());
		setListData(resourceModels.toArray());
	}

	/**
	 *  Return array list of resource model
	 * 
	 * @return      array list of resource model
	 */

	public ArrayList<ResourceModel> getResourceModelArray() {
		return resourceModels;
	}
	/**
	 *  Return whether this component is RBT (Recursive Branching Tree) 
	 * 
	 * @return boolean
	 */
	public boolean isRBT() {
		return false;
	}
	/**
	 *  Return content of list(for debug)
	 * 
	 * @return      attributes of resource models in list
	 */

	public String toString() {
		StringBuffer buffer = new StringBuffer();
		//System.err.println("Resource Models : " + resourceModels.size());
		for (ResourceModel model : resourceModels) {
			buffer.append(model.toString());
			buffer.append("\n");
		}
		return buffer.toString();
	}
}
