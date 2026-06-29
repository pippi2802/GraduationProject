package edu.penn.rtg.schedulingapp.algo;


import edu.penn.rtg.schedulingapp.SchComponent;
import edu.penn.rtg.schedulingapp.TreeComponent;
import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.ResourceModelList;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.Task;
import edu.penn.rtg.schedulingapp.TaskList;
import edu.penn.rtg.schedulingapp.util.CartsProgress;
/**
 * ARINC Resource Model - Abstract Component Interface.
 * <P>
 * A component can be consisted of a set of sub-components or 
 * a set of periodic task. In case of a set of periodic tasks, we can consider 
 * them as a single periodic task which can schedule given periodic tasks. In case 
 * of a set of subcomponents, we can transform each component to single task. Then, 
 * we abstract them as a single task which can schedule all sub-components. 
 * In point of subcomponents, this single task can be considered as resource model 
 * supply certain amount of resouce allocation which is needed to schedule all sub-components.
 * <P>
 * (ARINC Resource Model)
 *
 * ARINC Resource Model consist of (O; J;T;C; D) tuple, where O is offset,J is jitter, T is period, 
 * C is worst case execution time, and D(<=T) is deadline. Jobs of this process are 
 * dispatched at time instants xT+O for every non-negative integer x, and each job 
 * will be released for execution at any time in the interval [xT+O; xT+O+J]. For such 
 * a process it is reasonable to assume that O <= D
 * <P>
 * computed Resource Model using abstract procedure is saved in component c
 * 
 * @author      
 * @version     1.0
 * @since       1.0
 */
public class ARINC {
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
	 * optimal bandwidth. This resource model bandwidth is then used to generate 
	 * the appropriate periodic resource model using one of the constructors of class 
	 * ResourceModel.
	 *
	 * @param  period given period
	 * @param  C	target component
	 * @return      resource model with given period.
	 * @see         ResourceModel
	 */

	protected ResourceModel generateInterface_periodic(int period, SchedulingComponent C)
			throws Exception {
		DMSchedulability_edp schedulability = new DMSchedulability_edp(C,
				period);
		double bandwidth = schedulability.getBandwidth();
		ResourceModel periodic = new ResourceModel(period, bandwidth, period);
		return periodic;
	}
	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period.
	 * @param  periodic target resource model
	 * @param  C	target component
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	protected Task transformInterface(ResourceModel periodic, SchedulingComponent C)
			throws Exception {
		DMSchedulability_edp schedulability = new DMSchedulability_edp(C, 0);
		return schedulability.T_DM_arinc(periodic);
	}

	/**
	 * Depending on the scheduling algorithm employed by object c, it calculate 
	 * optimal bandwidth(EDP resource model) . This resource model bandwidth is then used to generate 
	 * the appropriate periodic resource model using one of the constructors of class 
	 * ResourceModel.
	 *
	 * @param  period given period
	 * @param  C	target component
	 * @return      resource model with given period.
	 * @see         ResourceModel
	 */
	 ResourceModel generateInterface_edp(int period, SchedulingComponent C)
			throws Exception {
		DMSchedulability_arinc schedulability = new DMSchedulability_arinc(C,
				period);
		double bandwidth = schedulability.getBandwidth();
		double deadline = schedulability.getDeadline(bandwidth);
		ResourceModel edp = new ResourceModel(period, bandwidth, deadline);
		return edp;
	}

	/**
	 * Depending on the scheduling algorithm employed by object c, it transform 
	 * given resource model into a task with given period(EDP resource model). 
	 * @param  edp target resource model
	 * @param  period given period
	 * @param  SchedulingComponentGUI	target component
	 * @return      A Task characterizing a periodic task with given period.
	 * @see         Task
	 */
	 protected Task transformInterface(ResourceModel edp, int period, SchedulingComponent C)
			throws Exception {
		DMSchedulability_edp schedulability = new DMSchedulability_edp(C, 0);
		return schedulability.T_DM(edp, period);
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
	 * structure as well as specific tasks from the ProcessedTaskList data structure
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
			ResourceModel rm = generateInterface_periodic(i, c);
			//if (!c.getCompName().equalsIgnoreCase("os scheduler"))
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

	public static String check(TreeComponent tc) throws Exception {
		if(tc.hasCriticalSection()) 
			return "SIRAP"; 
		if(!tc.isArincTask()) 
			return "EDP";
		for (TreeComponent child_tc : tc.getAllChildren()) {
			SchComponent child=child_tc.getSchCom();
			if(!child.isDM()) 
			{
				return "ARINC task is detected \n but Local scheduler of child component '"+child_tc.getCompName()+"' is not DM";
			}
			if(child_tc.hasChildren()) 
			{
				return "ARINC task is detected \n but Only 2-Level hierachical scheduling is supported.\nChild component '"
					+child_tc.getCompName()+"' has child components";

			}
		}
		return "ARINC";

	}

	// Given a tree of components following is a wrapper function that generates
	// all the interfaces. Our tool front end should call
	// this function passing it the tree, and it will return an Interface for
	// each component in the tree.
	// public Tree abstractionProcedure(Tree tree){

	// Iterate the following for each component in the tree
	// {
	// Get the component from the tree
	// Assume user has specified a list of period values to be used for the
	// interface. (We need to provide a mechanism where
	// users can specify a range of period values for each component's interface
	// (e.g., 3...100))
	// Iterate the following for each period in the given range
	// {
	// If the children of this component are all basic tasks
	// {
	// Call generateInterface
	// }
	// If the children are other components
	// {

	// First Call transformInterface to transform each child's resource model
	// into a task
	// Call generateInterface
	// }
	// }
	// }
	// }

}
