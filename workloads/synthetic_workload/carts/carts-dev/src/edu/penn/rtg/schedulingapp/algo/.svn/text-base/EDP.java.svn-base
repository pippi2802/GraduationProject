/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

package edu.penn.rtg.schedulingapp.algo;

import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.ResourceModelList;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.TaskList;
import edu.penn.rtg.schedulingapp.util.CartsProgress;

/**
 * EDP Resource Model - Abstract Component Interface.
 * <P>
 * A component can be consisted of a set of sub-components or 
 * a set of periodic task. In case of a set of periodic tasks, we can consider 
 * them as a single periodic task which can schedule given periodic tasks. In case 
 * of a set of subcomponents, we can transform each component to single task. Then, 
 * we abstract them as a single task which can schedule all sub-components. 
 * In point of subcomponents, this single task can be considered as resource model 
 * supply certain amount of resouce allocation which is needed to schedule all sub-components.
 * <P>
 * (EDP Resource Model)
 *
 * EDP Resource Model provides 'e' units of resource within 'd' time units, with this process 
 * repeating every 'p' time units.
 * <P>
 * computed Resource Model using abstract procedure is saved in component c
 * @author      
 * @version     1.0
 * @since       1.0
 */

public class EDP {
	CartsProgress cp;
	public void start(TreeComponent comp){
		int size=comp.getChildSize()+2;
		cp=new CartsProgress(size);
		cp.setVisible(true);
	}
	public void end(){
		cp.end();
	}


	/**
	 * Depending on the scheduling algorithm employed by object c, it calculate 
	 * optimal bandwidth by invoking either class EDFSchedulability_edp or class 
	 * DMSchedulability_edp. This resource model bandwidth is then used to generate 
	 * the appropriate periodic resource model using one of the constructors of class 
	 * ResourceModel.
	 *
	 * @param  period given period
	 * @param  C	target component
	 * @return      resource model with given period.
	 * @see         ResourceModel
	 */
	protected ResourceModel generateInterface(int period, SchedulingComponent C)
			throws Exception {

		if (C.isEDF()) {
			EDFSchedulability_edp schedulability = new EDFSchedulability_edp(C,
					period);
			double bandwidth = schedulability.getBandwidth();
			double deadline = schedulability.getDeadline(bandwidth * period);
			ResourceModel edp = new ResourceModel(period, bandwidth, deadline);
			return edp;
		} else {
			DMSchedulability_edp schedulability = new DMSchedulability_edp(C,
					period);
			double bandwidth = schedulability.getBandwidth();
			double deadline = schedulability.getDeadline(bandwidth * period);
			ResourceModel edp = new ResourceModel(period, bandwidth, deadline);
			return edp;
		}
	}

	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period.
	 * @param  edp target resource model
	 * @param  period given period
	 * @param  C	target component
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	protected Task transformInterface(ResourceModel edp, int period, SchedulingComponent C)
			throws Exception {

		if (C.isEDF()) {
			EDFSchedulability_edp schedulability = new EDFSchedulability_edp(C,
					period);
			return schedulability.T_EDF(edp);
		} else {
			DMSchedulability_edp schedulability = new DMSchedulability_edp(C,
					period);
			return schedulability.T_DM(edp, period);
		}
	}
	/**
	 * Abstract them as a single task which can schedule all sub-components.
	 * For each child of c that is also a SchedulingComponent object, the function
	 * iteratively calls itself using the child object as input. When all these iterative
	 * calls return, interfaces have been generated for all the SchedulingComponent
	 * objects which are present in the subtree rooted at c. In particular, for all the
	 * children of c that are SchedulingComponent objects, their ProcessedTaskList
	 * data structure contains the interface tasks. That is, it contains the list of tasks
	 * generated from Periodic resource models (one for each period value in the range
	 * [MinimumPeriod, MaximumPeriod]) that will be presented to c.
	 * <P>
	 * The tasks in the workload of c comprises of all the tasks in the TaskList data
	 * structure as well as specic tasks from the ProcessedTaskList data structure
	 * of its children. 
	 * <P>
	 * Function abstractionProcedure first invokes function generateInterface
	 * and then invokes function transformInterface for each period value i. gen-
	 * erateInterface returns a periodic resource model with period i, which is then
	 * transformed into a periodic task with period i by function transformInter-
	 * face. 
	 * <P>
	 * The resource model is stored in the ResourceModelList data structure
	 * and the transformed task is stored in the ProcessedTaskList data structure
	 * of object c. Further, if c has a parent SchedulingComponent object, then the
	 * tasks in ProcessedTaskList are also copied in the ChildrenToTaskTable
	 * data structure of the parent. Finally, the Processed boolean variable of c is
	 * set to true so that appropriate visual cues can be given in the GUI indicating
	 * that c has been processe
	 * @param  c	Target Component 
	 * @return      none
	 * @see         none
	 */
	public void abstractionProcedure(TreeComponent tc) throws Exception {
		if (tc.getAllChildren().size() != 0) {
			for (TreeComponent comp : tc.getAllChildren()) {
				abstractionProcedure(comp);
			}
		}
		cp.increment();
		SchedulingComponent c=(SchedulingComponent) tc.getSchCom();
		ResourceModelList list = new ResourceModelList();
		TaskList processed = new TaskList();
		for (int i = (int) c.getMinPeriod(); i <= (int) c.getMaxPeriod(); i++) {
			ResourceModel rm = generateInterface(i, c);
			list.getResourceModelArray().add(rm);
			processed.getTasks().add(transformInterface(rm, i, c));
		}

		tc.setProcessedTaskList(processed);
		tc.setResourceModelList(list);
		if (tc.hasParentComp()) {
			tc.getParentComp().getChildrenToTaskTable().put(tc, processed);
		}

		tc.setProcessed(true);
	}

	// Following is how a component should be created

	/*
	 * public RTSS07(int period){
	 * 
	 * this.Period = period; // Create Tasks T11 = new Task(45,2,25); T12 = new
	 * Task(65,3,30); T13 = new Task(85,4,40);
	 * 
	 * tasks.add(T11); tasks.add(T12); tasks.add(T13); C1 = new Component(tasks,
	 * 1); // 1 means EDF scheduler and 2 means DM scheduler }
	 */

	// Given a tree of components following is a wrapper function that generates
	// all the interfaces. Our tool front end should call
	// this function passing it the tree, and it will return an Interface for
	// each component in the tree.
	/*
	 * void abstractionProcedure(RootComponent root){
	 * 
	 * 
	 * if(root.getAllChildren().size() != 0) { for(SchedulingComponent c :
	 * root.getAllChildren()) { abstractionProcedure(c); } // Get the component
	 * from the tree // Assume user has specified a list of period values to be
	 * used for the interface. (We need to provide a mechanism where // users
	 * can specify a range of period values for each component's interface
	 * (e.g., 3...100)) // Iterate the following for each period in the given
	 * range { // If the children of this component are all basic tasks { //
	 * Call generateInterface } // If the children are other components {
	 * 
	 * // First Call transformInterface to transform each child's resource model
	 * into a task // Call generateInterface } } ResourceModelList list = new
	 * ResourceModelList(); TaskList processed = new TaskList(); for(int i =
	 * (int)root.getMinimumPeriod(); i <= (int)root.getMaximumPeriod(); i++) {
	 * ResourceModel rm = generateInterface(i, c);
	 * list.getResourceModelArray().add(rm);
	 * processed.getTasks().add(transformInterface(rm, i, c)); }
	 * 
	 * c.setProcessedTaskList(processed); c.setResourceModelList(list); }
	 * 
	 * return;
	 * 
	 * 
	 * }
	 */

}
